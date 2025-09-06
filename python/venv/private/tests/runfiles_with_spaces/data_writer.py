"""Read data from a file and write it to an output."""

import argparse
from pathlib import Path

from python.runfiles import Runfiles


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    def _bazel_str_with_space(value: str) -> str:
        """Process arguments from Bazel location expansions

        Bazel wraps `rlocationpath` values with `'` characters which are required
        to be stripped if they're to be used by the Runfiles API.
        """
        return value.strip("'")

    def _bazel_path_with_space(value: str) -> Path:
        return Path(_bazel_str_with_space(value))

    parser.add_argument(
        "--data",
        required=True,
        type=_bazel_str_with_space,
        help="The rlocationpath to read.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=_bazel_path_with_space,
        help="The file to write to.",
    )

    return parser.parse_args()


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


def main() -> None:
    """The main entrypoint"""
    args = parse_args()
    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles.")

    data_file = _rlocation(runfiles, args.data)

    text = data_file.read_text(encoding="utf-8")

    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(text.upper(), encoding="utf-8")


if __name__ == "__main__":
    main()
