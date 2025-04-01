"""A smalls script for writing files."""

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()

    parser.add_argument("--output", type=Path, required=True, help="The output path.")

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    args.output.write_bytes(b"La-Li-Lu-Le-Lo\n")


if __name__ == "__main__":
    main()
