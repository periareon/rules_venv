"""A tool for building a runfiles zip file for use in environments that don't support runfiles directories

This primarily exists due to the lack of:
https://github.com/bazelbuild/bazel/issues/15486
"""

import argparse
import logging
import os
import stat
import zipfile
from pathlib import Path
from typing import List, Tuple

RlocationPath = str

def _srcs_pair_arg_file(arg: str) -> List[Tuple[Path, RlocationPath]]:
    if not arg.startswith("@"):
        raise ValueError(f"Expected a params file. Got `{arg}`")

    args_file = Path(arg[1:])

    pairs = []
    for line in args_file.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]
        src, _, dest = text.partition("=")
        if not src or not dest:
            raise ValueError(f"Unexpected src pair: {line}")
        pairs.append((Path(src), dest))

    return pairs


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output", type=Path, required=True, help="The path to the output zip file"
    )

    parser.add_argument(
        "src_pairs",
        nargs=1,
        type=_srcs_pair_arg_file,
        help="Source files to include in runfiles.",
    )

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    if "RULES_VENV_RUNFILES_DEBUG" in os.environ:
        logging.basicConfig(level=logging.DEBUG)

    args.output.parent.mkdir(exist_ok=True, parents=True)
    with zipfile.ZipFile(str(args.output), "w") as zip_file:
        for pair in args.src_pairs:
            for src, dest in pair:
                info = zipfile.ZipInfo(filename=dest, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                st_mode = src.stat().st_mode
                info.external_attr = st_mode << 16

                logging.debug(
                    "Writing runfile file to zip: %s -> %s (%s)",
                    str(src),
                    dest,
                    stat.filemode(st_mode),
                )
                with src.open("rb") as f:
                    zip_file.writestr(info, f.read())


if __name__ == "__main__":
    main()
