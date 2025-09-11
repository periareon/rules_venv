"""A script for updating the pytest entrypoint to be ignored by common linters."""

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="The location of the output file to write.",
    )
    parser.add_argument(
        "--entrypoint",
        type=Path,
        required=True,
        help="The location of the entrypoint to read.",
    )

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    content = args.entrypoint.read_text(encoding="utf-8")

    args.output.write_text(
        "\n".join(
            [
                "# type: ignore",
                "# pylint: skip-file",
                content,
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
