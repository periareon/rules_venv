"""Entry point for running Mypy from Bazel."""

import argparse
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence, TextIO, Union

# Running pylint on the mypy import causes a crash
# pylint: disable=all
from mypy.main import main as mypy_main
from python.runfiles import Runfiles

# pylint: enable=all


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
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config-file",
        required=True,
        type=_maybe_runfile,
        help="The configuration file (mypy.ini).",
    )
    parser.add_argument(
        "--file",
        dest="sources",
        action="append",
        type=_maybe_runfile,
        required=True,
        help="The source file to run mypy on.",
    )
    parser.add_argument(
        "--workspace_name",
        type=str,
        required=True,
        help="The name of current workspace. Used to include the appropriate runfiles directory to `MYPYPATH`.",
    )
    parser.add_argument(
        "--marker",
        type=Path,
        help="The file to create as an indication that the action succeeded.",
    )

    parsed_args = parser.parse_args(args)

    if not parsed_args.sources:
        parser.error("No source files were provided.")

    return parsed_args


def _mypy_path(workspace_name: str) -> str:
    """Compute the `MYPYPATH` variable from the current environment."""
    mypy_path = os.getenv("MYPYPATH", "").split(os.pathsep)

    if "PY_VENV_RUNFILES_DIR" in os.environ:
        runfiles_dir = Path(os.environ["PY_VENV_RUNFILES_DIR"])
    elif "RUNFILES_DIR" in os.environ:
        runfiles_dir = Path(os.environ["RUNFILES_DIR"])
    else:
        raise EnvironmentError("Failed to locate runfiles")

    return os.pathsep.join([str(runfiles_dir / workspace_name)] + mypy_path)


def main() -> None:
    """Mypy test runner main entry point."""
    if "BAZEL_TEST" in os.environ and "PY_MYPY_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["PY_MYPY_RUNNER_ARGS_FILE"])
        args = parse_args(arg_file.read_text(encoding="utf-8").splitlines())
    else:
        args = parse_args()

    stream = io.StringIO()
    stderr: Union[TextIO, io.StringIO]
    stdout: Union[TextIO, io.StringIO]
    if args.marker:
        stderr = stream
        stdout = stream
    else:
        stderr = sys.stderr
        stdout = sys.stdout

    tmp_dir = Path(tempfile.mkdtemp(prefix="bazel-mypy-", dir=os.getenv("TEST_TMPDIR")))
    exit_code = 0
    try:
        os.environ["HOME"] = str(tmp_dir)
        os.environ["USERPROFILE"] = str(tmp_dir)
        os.environ["MYPYPATH"] = _mypy_path(args.workspace_name)

        mypy_args = [
            "--config-file",
            str(args.config_file),
            "--cache-dir",
            str(tmp_dir / "mypy_cache"),
            "--no-incremental",
        ] + [str(src) for src in args.sources]

        mypy_main(args=mypy_args, stdout=stdout, stderr=stderr, clean_exit=True)

    except SystemExit as exc:
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, str):
            exit_code = int(exc.code)
        else:
            exit_code = exc.code

    finally:
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
