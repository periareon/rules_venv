"""A binary that takes --output and writes text to a file."""

import argparse
from pathlib import Path

from python.pex.private.tests.deps.dep_a.dep_a import get_messages as get_messages_a
from python.pex.private.tests.deps.dep_b.dep_b import get_messages as get_messages_b


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

    # Collect all messages from dependencies
    all_messages = []
    all_messages.extend(get_messages_a())
    all_messages.extend(get_messages_b())

    # Write messages to output file
    args.output.parent.mkdir(exist_ok=True, parents=True)
    content = "\n".join(all_messages) + "\n"
    args.output.write_bytes(content.encode("utf-8"))


if __name__ == "__main__":
    main()
