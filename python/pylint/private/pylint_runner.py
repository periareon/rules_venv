"""A script for running pylint within Bazel."""

import argparse
import contextlib
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Generator, Optional, Sequence

from pylint import run_pylint
from python.runfiles import Runfiles  # type: ignore


def _no_realpath(path, **_kwargs):  # type: ignore
    """Redirect realpath, with any keyword args, to abspath."""
    return os.path.abspath(path)


@contextlib.contextmanager
def determinisim_patch() -> Generator[None, None, None]:
    """A context manager for applying deterministic behavior to the python stdlib."""

    # Avoid sandbox escapes
    old_realpath = os.path.realpath
    os.path.realpath = _no_realpath  # type: ignore

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
    parser = argparse.ArgumentParser("Pylint Runner")

    parser.add_argument(
        "--rcfile",
        required=True,
        type=_maybe_runfile,
        help="The configuration file (`pylintrc.toml`).",
    )
    parser.add_argument(
        "--marker",
        type=_maybe_runfile,
        help="The file to create as an indication that the 'PyPylint' action succeeded.",
    )
    parser.add_argument(
        "--src",
        dest="sources",
        action="append",
        type=_maybe_runfile,
        required=True,
        help="A source file to run pylint on.",
    )

    parsed_args = parser.parse_args(args)

    if not parsed_args.sources:
        parser.error("No source files were provided.")

    return parsed_args


def _load_args() -> Sequence[str]:
    """Load command line arguments from the environment."""
    if "BAZEL_TEST" in os.environ and "PY_PYLINT_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["PY_PYLINT_RUNNER_ARGS_FILE"])
        return arg_file.read_text(encoding="utf-8").splitlines()

    return sys.argv[1:]


def _report_logs(log_dir: Path) -> None:
    """Print additional logs such as pytest crash logs to stderr."""
    logs = []
    for entry in log_dir.iterdir():
        if not entry.is_file():
            continue

        if not entry.name.startswith("pylint-crash"):
            continue

        logs.append(entry)

    if not logs:
        return

    delimiter = "-" * 80
    print(delimiter, file=sys.stdout)
    print("rules_pylint: Reporting additional log files", file=sys.stdout)
    print(delimiter, file=sys.stdout)
    for entry in logs:
        print(delimiter, file=sys.stdout)
        print(f"Log file: {entry}", file=sys.stdout)
        print(delimiter, file=sys.stdout)
        print(entry.read_text(encoding="utf-8"), file=sys.stdout)
        print(delimiter, file=sys.stdout)


def main() -> None:
    """The main entrypoint."""
    args = parse_args(_load_args())

    old_stderr = sys.stderr
    old_stdout = sys.stdout

    stream = io.StringIO()
    if args.marker:
        sys.stderr = stream
        sys.stdout = stream

    exit_code = 0
    tmp_dir = tempfile.mkdtemp(prefix="bazel-pylint-", dir=os.getenv("TEST_TMPDIR"))
    try:
        os.environ["HOME"] = str(tmp_dir)
        os.environ["USERPROFILE"] = str(tmp_dir)
        os.environ["PYLINTHOME"] = str(tmp_dir)

        pylint_args = [
            "--rcfile",
            str(args.rcfile),
        ] + [str(src) for src in args.sources]

        with determinisim_patch():
            run_pylint(pylint_args)

    except SystemExit as exc:
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, str):
            exit_code = int(exc.code)
        else:
            exit_code = exc.code

    finally:
        _report_logs(Path(tmp_dir))

        if args.marker:
            sys.stderr = old_stderr
            sys.stdout = old_stdout

        if "TEST_TMPDIR" not in os.environ:
            shutil.rmtree(tmp_dir)

    if args.marker:
        if exit_code == 0:
            args.marker.write_bytes(b"")
        else:
            print(stream.getvalue(), file=sys.stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
