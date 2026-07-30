"""A script for running ruff within Bazel."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from python.runfiles import Runfiles


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists."""
    runfile = runfiles.Rlocation(rlocationpath, source_repo=os.getenv("TEST_WORKSPACE"))
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def _maybe_runfile(arg: str) -> Path:
    """Parse an argument into a path while resolving runfiles.

    Not all contexts this script runs in will use runfiles. In
    these cases the function is a noop.
    """
    if "BAZEL_TEST" not in os.environ:
        return Path(arg)

    runfiles = Runfiles.Create()
    if not runfiles:
        raise OSError("Failed to locate runfiles")
    return _rlocation(runfiles, arg)


class Modes(StrEnum):
    """Supported modes for `ruff`."""

    CHECK = "check"
    """Run linting"""

    FORMAT = "format"
    """Run formatting"""


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser("Ruff Runner")

    parser.add_argument(
        "--config",
        required=True,
        type=_maybe_runfile,
        help="The configuration file (`ruff.toml` or `pyproject.toml`).",
    )
    parser.add_argument(
        "--mode",
        type=Modes,
        required=True,
        help="Whether to run `ruff check` or `ruff format`.",
    )
    parser.add_argument(
        "--ruff",
        type=_maybe_runfile,
        default=None,
        help="The `ruff` binary.",
    )
    parser.add_argument(
        "--marker",
        type=_maybe_runfile,
        help="The file to create as an indication that the 'Ruff' action succeeded.",
    )
    parser.add_argument(
        "--src",
        dest="sources",
        action="append",
        type=_maybe_runfile,
        required=True,
        help="A source file to run ruff on.",
    )
    parser.add_argument(
        "--first-party-module",
        dest="first_party_modules",
        action="append",
        default=[],
        help=(
            "A top-level module name to treat as first-party for isort "
            "classification. Repeatable. Computed by the aspect/test rule "
            "at analysis time so no runtime workspace walk is needed."
        ),
    )

    parsed_args = parser.parse_args(args)

    if not parsed_args.sources:
        parser.error("No source files were provided.")

    return parsed_args


def _load_args() -> Sequence[str]:
    """Load command line arguments from the environment."""
    if "BAZEL_TEST" in os.environ and "RULES_VENV_RUFF_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise OSError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["RULES_VENV_RUFF_RUNNER_ARGS_FILE"])
        return arg_file.read_text(encoding="utf-8").splitlines()

    return sys.argv[1:]


def find_ruff(ruff_path: Path | None = None) -> Path:
    """Locate ruff.

    If `ruff_path` is passed, it wins. Otherwise fall back to importing the
    `ruff` PyPI package and locating its bundled binary.
    """
    if ruff_path is not None:
        return ruff_path

    try:
        # pylint: disable-next=import-outside-toplevel
        import ruff  # type: ignore
    except ImportError as exc:
        raise ModuleNotFoundError(
            "No ruff binary was provided and ruff is not importable"
        ) from exc

    try:
        ruff_str = ruff.find_ruff_bin()
        if ruff_str:
            return Path(ruff_str)
    except FileNotFoundError:
        pass

    # Fallback for repository rules whose data path to the binary differs
    # from what `find_ruff_bin` expects (e.g. `rules_req_compile`).
    ruff_module_path = Path(ruff.__file__)
    ruff_site_packages = ruff_module_path.parent.parent
    ruff_version: str | None = None
    for entry in ruff_site_packages.iterdir():
        if entry.name.endswith(".data"):
            _, _, ruff_version = entry.name[: -len(".data")].partition("-")
            break

    if ruff_version:
        ruff_scripts_dir = ruff_site_packages / f"ruff-{ruff_version}.data/scripts"
        for candidate in (ruff_scripts_dir / "ruff", ruff_scripts_dir / "ruff.exe"):
            if candidate.exists():
                return candidate

    raise FileNotFoundError("Failed to locate ruff binary.")


def user_known_first_party(config_path: Path) -> list[str]:
    """Read `lint.isort.known-first-party` from the user's ruff config."""
    try:
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return []

    # `ruff.toml` uses top-level keys; `pyproject.toml` nests under `tool.ruff`.
    root = (
        data.get("tool", {}).get("ruff", {})
        if config_path.name == "pyproject.toml"
        else data
    )
    values = root.get("lint", {}).get("isort", {}).get("known-first-party", [])
    if not isinstance(values, list):
        return []
    return [str(v) for v in values if isinstance(v, str)]


def _first_party_config_override(
    explicit_modules: Sequence[str], user_config: Path
) -> str | None:
    """Build a `lint.isort.known-first-party` override.

    The aspect / test rule enumerates workspace first-party modules at
    analysis time (from `PyInfo.transitive_sources`, deduped by the top
    workspace-relative segment) and hands them in via `--first-party-module`.
    We merge those with anything the user's config already declares so
    isort classification is stable regardless of what happens to be in the
    sandbox.
    """
    combined = set(explicit_modules) | set(user_known_first_party(user_config))
    if not combined:
        return None
    quoted = ", ".join(json.dumps(name) for name in sorted(combined))
    return f"lint.isort.known-first-party = [{quoted}]"


def main() -> None:
    """The main entrypoint."""
    args = parse_args(_load_args())

    ruff = find_ruff(args.ruff)

    is_test = "BAZEL_TEST" in os.environ

    tmp_dir = tempfile.mkdtemp(prefix="bazel-ruff-", dir=os.getenv("TEST_TMPDIR"))

    ruff_args = [
        str(ruff),
        "--config",
        str(args.config),
    ]

    first_party_override = _first_party_config_override(
        args.first_party_modules, args.config
    )
    if first_party_override is not None:
        ruff_args.extend(["--config", first_party_override])
        if "RULES_VENV_RUFF_DEBUG" in os.environ:
            print(
                f"ruff-runner: first-party override: {first_party_override}",
                file=sys.stderr,
            )

    ruff_args.append(str(args.mode))

    if args.mode == Modes.FORMAT:
        ruff_args.append("--diff")

    ruff_args.extend([str(src) for src in args.sources])

    env = {
        "HOME": str(tmp_dir),
        "USERPROFILE": str(tmp_dir),
        "RUFF_CACHE_DIR": str(tmp_dir),
    }

    if "RULES_VENV_RUFF_DEBUG" in os.environ:
        ruff_args.append("--verbose")

    result = subprocess.run(
        ruff_args,
        stdout=None if is_test else subprocess.PIPE,
        stderr=None if is_test else subprocess.STDOUT,
        env=env,
        check=False,
    )

    if "TEST_TMPDIR" not in os.environ:
        shutil.rmtree(tmp_dir)

    if args.marker:
        if result.returncode == 0:
            args.marker.write_bytes(b"")
        elif not is_test:
            sys.stderr.write(result.stdout.decode("utf-8"))

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
