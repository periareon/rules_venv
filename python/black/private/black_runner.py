"""A script for running black within Bazel."""

import argparse
import contextlib
import os
import platform
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Generator, Optional, Sequence, cast

import black
from python.runfiles import Runfiles


@contextlib.contextmanager
def determinism_patch() -> Generator[None, None, None]:
    """A context manager for applying deterministic behavior to the python stdlib."""

    def _no_realpath(path, **kwargs):  # type: ignore
        """Avoid resolving symlinks and instead, simply convert paths to absolute."""
        del kwargs
        return os.path.abspath(path)

    # Avoid sandbox escapes
    old_realpath = os.path.realpath
    os.path.realpath = cast(Any, _no_realpath)

    try:
        yield
    finally:
        os.path.realpath = old_realpath


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
    """
    # TODO: https://github.com/periareon/rules_venv/issues/37
    source_repo = None
    if platform.system() == "Windows":
        source_repo = ""
    runfile = runfiles.Rlocation(rlocationpath, source_repo)
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def _maybe_runfile(arg: str) -> Path:
    """Parse an argument into a path while resolving runfiles.

    Not all contexts this script runs in will use runfiles. In
    these cases the functon is a noop.
    """
    if "BAZEL_TEST" not in os.environ:
        return Path(arg)

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles")
    return _rlocation(runfiles, arg)


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser("Black Runner")

    parser.add_argument(
        "--config",
        required=True,
        type=_maybe_runfile,
        help="The configuration file (`pyproject.toml`).",
    )
    parser.add_argument(
        "--marker",
        type=_maybe_runfile,
        help="The file to create as an indication that the 'PyBlack' action succeeded.",
    )
    parser.add_argument(
        "--src",
        dest="sources",
        action="append",
        type=_maybe_runfile,
        required=True,
        help="A source file to run black on.",
    )

    parsed_args = parser.parse_args(args)

    if not parsed_args.sources:
        parser.error("No source files were provided.")

    return parsed_args


def _load_args() -> Sequence[str]:
    """Load command line arguments from the environment."""
    if "BAZEL_TEST" in os.environ and "RULES_VENV_BLACK_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["RULES_VENV_BLACK_RUNNER_ARGS_FILE"])
        return arg_file.read_text(encoding="utf-8").splitlines()

    return sys.argv[1:]


def main() -> None:
    """The main entrypoint."""
    args = parse_args(_load_args())

    black_args = [
        "--check",
        "--diff",
        "--config",
        str(args.config),
    ] + [str(src) for src in args.sources]

    old_argv = list(sys.argv)
    sys.argv = [sys.argv[0]] + black_args

    exit_code = 0
    tmp_dir = tempfile.mkdtemp(prefix="bazel-black-", dir=os.getenv("TEST_TMPDIR"))

    stream = Path(tmp_dir) / "stream"

    os.environ["HOME"] = str(tmp_dir)
    os.environ["USERPROFILE"] = str(tmp_dir)

    with determinism_patch():
        try:
            # If a stream is defined, ensure the output is captured to this file.
            if args.marker:
                with stream.open("w", encoding="utf-8") as tmp:
                    with redirect_stderr(tmp), redirect_stdout(tmp):
                        black.patched_main()
            else:
                black.patched_main()

        except SystemExit as exc:
            if exc.code is None:
                exit_code = 0
            elif isinstance(exc.code, str):
                exit_code = int(exc.code)
            else:
                exit_code = exc.code

        finally:
            sys.argv = old_argv

    if args.marker:
        if exit_code == 0:
            args.marker.write_bytes(b"")
        else:
            print(stream.read_text(encoding="utf-8"), file=sys.stderr)

    if "TEST_TMPDIR" not in os.environ:
        shutil.rmtree(tmp_dir)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
