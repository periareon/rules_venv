"""A small test script that uses runfiles."""

import argparse
import os
import shutil
from pathlib import Path

from python.runfiles import Runfiles  # type: ignore


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
    """
    runfile = runfiles.Rlocation(rlocationpath)
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="The location where the output should be written.",
    )

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles.")

    # To further ensure this file is accessed from the runfiles of the copier, a alternate
    # file is added to at runtime via the `run_binary` target so `rlocationpath` can be used
    # to identify a sibling file from which we can get the correct `rlocationpath` without
    # having it as a direct input to the action.
    rlocationpath = os.environ["WRITER_OUTPUT_RLOCATIONPATH"].replace(
        "writer_expected.txt", "writer_output.txt"
    )

    src = _rlocation(runfiles, rlocationpath)

    args.output.parent.mkdir(exist_ok=True, parents=True)
    shutil.copy2(src, args.output)


if __name__ == "__main__":
    main()
