"""A script for printing a greeting."""

import argparse
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--output", type=Path, required=True, help="The output path.")

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()
    name = os.environ["EMBEDDED_ENV_NAME"]
    args.output.write_text(f"Hello, {name}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
