"""Process wrapper that generates a directory structure with nested files."""

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Generate a directory structure with nested files"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory path",
    )
    parser.add_argument(
        "--content",
        type=str,
        required=True,
        help="Content to write to the nested data.txt file",
    )

    return parser.parse_args()


def main() -> None:
    """The main entrypoint"""

    args = parse_args()

    # Create the output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Create nested directory structure
    nested_dir = args.output / "subdir" / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)

    # Create a text file in the nested directory
    text_file = nested_dir / "data.txt"
    text_file.write_text(f"{args.content}\n", encoding="utf-8")

    # Create another file at the top level
    top_file = args.output / "top_level.txt"
    top_file.write_text("Top Level Content\n", encoding="utf-8")


if __name__ == "__main__":
    main()
