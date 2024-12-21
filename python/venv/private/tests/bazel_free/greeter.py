"""A script which is used to ensure binaries are usable outside of Bazel environments."""

import argparse
import os
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

    parser.add_argument("message", type=str, help="A string to print.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="A file to write to instead of printing.",
    )

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles.")

    prefix_file = _rlocation(runfiles, os.environ["PREFIX_RLOCATIONPATH"])

    prefix = prefix_file.read_text(encoding="utf-8").strip()
    greeting = f"{prefix} {args.message}"

    if args.output:
        args.output.parent.mkdir(exist_ok=True, parents=True)
        args.output.write_text(greeting, encoding="utf-8")
    else:
        print(greeting)


if __name__ == "__main__":
    main()
