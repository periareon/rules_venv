"""A script for running ruff within Bazel."""

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Optional, Sequence

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
        str(args.mode),
    ]

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
