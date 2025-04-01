"""A smalls script for writing files."""

import argparse
from pathlib import Path

from python.runfiles import Runfiles  # type: ignore


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()

    parser.add_argument("--output", type=Path, required=True, help="The output path.")

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
    """The main entrypoint."""
    args = parse_args()

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles.")

    runfile = _rlocation(
        runfiles,
        "rules_venv/python/venv/private/tests/zipapp/with_runfiles/data.txt",
    )

    text = runfile.read_text(encoding="utf-8").strip()
    args.output.write_bytes(f"{text}\n".encode("utf-8"))


if __name__ == "__main__":
    main()
