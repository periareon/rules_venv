"""A utility for uploading wheels using twine."""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence

from python.runfiles import Runfiles  # type: ignore

# isort: off

try:
    from twine.__main__ import main as twine_main
except (ImportError, ModuleNotFoundError):
    print("Twine not configured. Publishing is not supported.", file=sys.stderr)
    sys.exit(1)


def _rlocation(runfiles: Optional[Runfiles], rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
    """
    if runfiles is None:
        raise EnvironmentError("Runfiles could not be found")
    runfile = runfiles.Rlocation(rlocationpath, "")
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def parse_args(
    args: Optional[Sequence[str]] = None, runfiles: Optional[Runfiles] = None
) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    def _rlocationpath(value: str) -> Path:
        return _rlocation(runfiles, value)

    parser.add_argument(
        "--wheel",
        required=True,
        type=_rlocationpath,
        help="The repository (package index) URL to upload the wheel to.",
    )

    parser.add_argument(
        "--wheel_name_file",
        required=True,
        type=_rlocationpath,
        help="The repository (package index) URL to upload the wheel to.",
    )

    parser.add_argument(
        "--repository_url",
        type=str,
        help="The repository (package index) URL to upload the wheel to.",
    )

    return parser.parse_args(args)


def main() -> Any:
    """The main entrypoint."""
    runfiles = Runfiles.Create()

    if "PY_WHEEL_PUBLISHER_ARGS" not in os.environ:
        raise EnvironmentError("PY_WHEEL_PUBLISHER_ARGS not defined in environment.")

    args_file = _rlocation(runfiles, os.environ["PY_WHEEL_PUBLISHER_ARGS"])
    argv = args_file.read_text(encoding="utf-8").splitlines()
    args = parse_args(argv, runfiles)

    wheel_filename = args.wheel_name_file.read_text(encoding="utf-8").strip()

    # Create a directory with the correctly named wheel
    with tempfile.TemporaryDirectory(prefix="bzl_wheel_publish-") as tmp_dir:
        wheel = Path(tmp_dir) / wheel_filename
        shutil.copy2(args.wheel, wheel)

        twine_args = [
            "upload",
            str(wheel),
        ]
        if args.repository_url:
            twine_args.extend(
                [
                    "--repository-url",
                    args.repository_url,
                ]
            )
        twine_args.extend(sys.argv[1:])

        sys.argv = sys.argv[:1] + twine_args

        return twine_main()


if __name__ == "__main__":
    main()
