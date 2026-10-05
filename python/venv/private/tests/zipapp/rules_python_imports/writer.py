"""A small script for writing files.

Unlike the `zipapp/rules_python_input` test, nothing here depends on a
`rules_venv` target, so the only thing that can put the workspace root on
`sys.path` is `py_venv_zipapp` itself. A stock `py_binary` relies on the
`rules_python` bootstrap for that and advertises nothing in `PyInfo.imports`.
"""

import argparse
from pathlib import Path

from python.venv.private.tests.zipapp.rules_python_imports import lib


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()

    parser.add_argument("--output", type=Path, required=True, help="The output path.")

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    args.output.write_bytes(f"{lib.TEXT}\n".encode())


if __name__ == "__main__":
    main()
