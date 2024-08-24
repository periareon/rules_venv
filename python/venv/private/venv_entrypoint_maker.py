"""A script for rendering a `py_venv_*` executable's entrypoint."""

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="The path to the output zip file",
    )
    parser.add_argument(
        "--template",
        type=Path,
        required=True,
        help="The template file to replace substitutions with.",
    )
    parser.add_argument(
        "--substitutions",
        type=json.loads,
        required=True,
        help="A json encoded mapping of substitutions to apply.",
    )
    parser.add_argument(
        "--file_substitutions",
        type=json.loads,
        required=True,
        help="A json encoded mapping of substitutions to apply.",
    )

    return parser.parse_args()


_VENDORED_TEMPLATE = """\
################################################################################
## rules_venv vendor: {file}
################################################################################
{content}
################################################################################
## rules_venv end vendor: {file}
################################################################################
"""


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    content = args.template.read_text(encoding="utf-8")
    for key, value in args.substitutions.items():
        content = content.replace(key, value)
    for key, file in args.file_substitutions.items():
        value = Path(file).read_text(encoding="utf-8")
        content = content.replace(
            key, _VENDORED_TEMPLATE.format(file=file, content=value)
        )

    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(content, encoding="utf-8")

    args.output.chmod(args.output.stat().st_mode | 0o100)


if __name__ == "__main__":
    main()
