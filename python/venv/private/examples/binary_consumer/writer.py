"""A small test script."""

import argparse
from pathlib import Path


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
    args.output.write_bytes("La-Li-Lu-Le-Lo.\n".encode("utf-8"))


if __name__ == "__main__":
    main()
