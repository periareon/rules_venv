"""A small test script."""

import argparse
from pathlib import Path

from python.venv.private.tests.binary_multi_source.special_message import (
    SPECIAL_MESSAGE,
)


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

    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_bytes(f"{SPECIAL_MESSAGE}\n".encode("utf-8"))


if __name__ == "__main__":
    main()
