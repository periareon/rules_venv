"""A script for running ruff within Bazel."""

import argparse
import io
import json
import keyword
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from python.runfiles import Runfiles


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runfile.
    """
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
        raise EnvironmentError("Failed to locate runfiles")
    return _rlocation(runfiles, arg)


class Modes(StrEnum):
    """Supported modes for `ruff`."""

    CHECK = "check"
    """Run linting"""

    FORMAT = "format"
    """Run formatting"""


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
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
        help="The `ruff` binary.",
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

    parsed_args = parser.parse_args(args)

    if not parsed_args.sources:
        parser.error("No source files were provided.")

    return parsed_args


def _load_args() -> Sequence[str]:
    """Load command line arguments from the environment."""
    if "BAZEL_TEST" in os.environ and "RULES_VENV_RUFF_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["RULES_VENV_RUFF_RUNNER_ARGS_FILE"])
        return arg_file.read_text(encoding="utf-8").splitlines()

    return sys.argv[1:]


def find_ruff(ruff_path: Optional[Path] = None) -> Path:
    """Locate ruff from the python environment

    Args:
        ruff_path: An override to enforce the desired binary.

    Returns:
        The path to the ruff binary to use.
    """

    if ruff_path is None:
        try:
            # pylint: disable-next=import-outside-toplevel
            import ruff  # type: ignore

            try:
                ruff_str = ruff.find_ruff_bin()
                if ruff_str:
                    ruff_path = Path(ruff_str)
            except FileNotFoundError:
                # Depending on the repository rule used to provide ruff, the data path to
                # the binary may differ. If the nominal lookup does not pass then fall back
                # to something known to work with at least `rules_req_compile`.
                ruff_module_path = Path(ruff.__file__)
                ruff_site_packages = ruff_module_path.parent.parent
                ruff_version = None
                for entry in ruff_site_packages.iterdir():
                    if entry.name.endswith(".data"):
                        _, _, ruff_version = entry.name[: -len(".data")].partition("-")
                        break

                if ruff_version:
                    ruff_scripts_dir = (
                        ruff_site_packages / f"ruff-{ruff_version}.data/scripts"
                    )

                    ruff_path = ruff_scripts_dir / "ruff"
                    if not ruff_path.exists():
                        ruff_path = ruff_scripts_dir / "ruff.exe"

        except ImportError as exc:
            raise ModuleNotFoundError(
                "No ruff binary was provided and ruff is not importable"
            ) from exc

    if not ruff_path:
        raise FileNotFoundError("Failed to locate ruff binary.")

    return ruff_path


_PY_SUFFIXES = (".py", ".pyi")


def _is_valid_module_name(name: str) -> bool:
    """Return True if `name` is a legal top-level Python module identifier."""
    return bool(name) and name.isidentifier() and not keyword.iskeyword(name)


def _dir_has_python_content(root: Path) -> bool:
    """Return True if `root` (a directory) contains any `.py` / `.pyi` file."""
    try:
        for entry in root.rglob("*"):
            if entry.is_file() and entry.suffix in _PY_SUFFIXES:
                return True
    except OSError:
        return False
    return False


def collect_first_party_names_from_dir(root: Path) -> List[str]:
    """Collect first-party module names from the top level of ``root``.

    Includes a top-level entry when its name is a valid Python identifier
    AND either the entry is a ``.py`` / ``.pyi`` file or the directory holds
    Python source content. Non-Python top-level dirs (``docs/`` etc.) are
    skipped so they don't collide with third-party pip packages of the same
    name.
    """
    names: List[str] = []
    if not root.is_dir():
        return names
    try:
        entries = list(root.iterdir())
    except OSError:
        return names
    for entry in entries:
        name = entry.name
        if name.startswith("."):
            continue
        if entry.is_file():
            stem = entry.stem if entry.suffix in _PY_SUFFIXES else None
            if stem and _is_valid_module_name(stem):
                names.append(stem)
        elif entry.is_dir():
            if _is_valid_module_name(name) and _dir_has_python_content(entry):
                names.append(name)
    return names


def _decode_manifest_key(escaped: str) -> str:
    """Decode a runfiles manifest key that used the escape encoding."""
    return escaped.replace(r"\s", " ").replace(r"\n", "\n").replace(r"\b", "\\")


def collect_first_party_names_from_manifest(  # pylint: disable=too-many-locals,too-many-branches
    manifest_file: Path, prefix: str
) -> List[str]:
    """Collect first-party names by parsing a runfiles manifest under ``prefix``.

    Used when no materialized runfiles directory is available (e.g. Windows
    Bazel with ``--enable_runfiles=false``, where only
    ``RUNFILES_MANIFEST_FILE`` is set).
    """
    normalized = prefix.rstrip("/") + "/"
    dir_has_py: Dict[str, bool] = {}
    root_files: Dict[str, None] = {}
    try:
        with manifest_file.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.rstrip("\n")
                if not line:
                    continue
                if line.startswith(" "):
                    key_field, _, _ = line[1:].partition(" ")
                    rlp = _decode_manifest_key(key_field)
                else:
                    rlp, _, _ = line.partition(" ")
                if not rlp.startswith(normalized):
                    continue
                rest = rlp[len(normalized) :]
                head, sep, tail = rest.partition("/")
                if not head or head.startswith("."):
                    continue
                if sep:
                    is_py = tail.endswith(_PY_SUFFIXES)
                    prior = dir_has_py.get(head, False)
                    dir_has_py[head] = prior or is_py
                else:
                    root_files[head] = None
    except OSError:
        return []

    names: List[str] = []
    for name, has_py in dir_has_py.items():
        if has_py and _is_valid_module_name(name):
            names.append(name)
    for name in root_files:
        stem, dot, suffix = name.rpartition(".")
        if dot and ("." + suffix) in _PY_SUFFIXES and _is_valid_module_name(stem):
            names.append(stem)
    return names


def user_known_first_party(config_path: Path) -> List[str]:
    """Read `lint.isort.known-first-party` from a user's ruff config."""
    try:
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return []

    # `ruff.toml` uses top-level keys; `pyproject.toml` nests them under `tool.ruff`.
    if config_path.name == "pyproject.toml":
        root = data.get("tool", {}).get("ruff", {})
    else:
        root = data

    isort_section = root.get("lint", {}).get("isort", {})
    values = isort_section.get("known-first-party", [])
    if not isinstance(values, list):
        return []
    return [str(v) for v in values if isinstance(v, str)]


def _iter_workspace_first_party_names(
    workspace: str, runfiles: Optional[Runfiles]
) -> Iterable[str]:
    """Yield first-party names discovered under `<workspace>/` in runfiles."""
    if runfiles is not None:
        resolved = runfiles.Rlocation(workspace, source_repo=workspace)
        if resolved:
            root = Path(resolved)
            if root.is_dir():
                yield from collect_first_party_names_from_dir(root)
                return

    manifest_env = os.environ.get("RUNFILES_MANIFEST_FILE")
    if manifest_env:
        manifest_file = Path(manifest_env)
        if manifest_file.is_file():
            yield from collect_first_party_names_from_manifest(manifest_file, workspace)
            return


def _first_party_config_override(user_config: Path) -> Optional[str]:
    """Build a ``lint.isort.known-first-party`` override for the sandbox.

    Ruff's default src-walk classification is unreliable inside a Bazel
    action sandbox — only the target's declared deps are staged, so files
    that aren't in the closure look absent and get classified as
    third-party. We supply an explicit list by scanning workspace runfiles
    and merging with anything the user's ruff config already declares.
    """
    workspace = os.environ.get("RULES_VENV_BAZEL_WORKSPACE")
    if not workspace:
        return None

    runfiles = Runfiles.Create()
    discovered = list(_iter_workspace_first_party_names(workspace, runfiles))

    combined = set(discovered) | set(user_known_first_party(user_config))
    if not combined:
        return None

    quoted = ", ".join(json.dumps(name) for name in sorted(combined))
    return f"lint.isort.known-first-party = [{quoted}]"


def main() -> None:
    """The main entrypoint."""
    args = parse_args(_load_args())

    stream = io.StringIO()

    ruff = find_ruff(args.ruff)

    is_test = "BAZEL_TEST" in os.environ

    tmp_dir = tempfile.mkdtemp(prefix="bazel-ruff-", dir=os.getenv("TEST_TMPDIR"))

    ruff_args = [
        str(ruff),
        "--config",
        str(args.config),
    ]

    first_party_override = _first_party_config_override(args.config)
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
    if not is_test:
        stream.write(result.stdout.decode("utf-8"))

    if "TEST_TMPDIR" not in os.environ:
        shutil.rmtree(tmp_dir)

    if args.marker:
        if result.returncode == 0:
            args.marker.write_bytes(b"")
        else:
            print(stream.getvalue(), file=sys.stderr)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
