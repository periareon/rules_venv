"""A tool for building a runfiles zip file for use in environments that don't support runfiles directories

This primarily exists due to the lack of:
https://github.com/bazelbuild/bazel/issues/15486
"""

import argparse
import io
import json
import logging
import os
import zipfile
from pathlib import Path
from typing import List, Tuple

RlocationPath = str


def _srcs_pair_arg_file(arg: str) -> List[Tuple[str, RlocationPath]]:
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
        pairs.append((src, dest))

    return pairs


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output", type=Path, required=True, help="The path to the output file"
    )

    parser.add_argument(
        "src_pairs",
        nargs=1,
        type=_srcs_pair_arg_file,
        help="Source files to include in runfiles.",
    )

    return parser.parse_args()


def create_zip(args: argparse.Namespace) -> None:
    """Create zip file of runfiles.

    Args:
        args: Parsed command line arguments.
    """
    logging.debug("Loading runfiles data.")
    zip_infos: List[Tuple[zipfile.ZipInfo, bytes]] = []
    for pair in args.src_pairs:
        for src, dest in pair:

            # Ensure timestamps are ignored so outputs are reproducible.
            zip_infos.append(
                (
                    zipfile.ZipInfo(filename=dest, date_time=(1980, 1, 1, 0, 0, 0)),
                    Path(src).read_bytes(),
                )
            )

    logging.debug("Building zipfile.")
    ram_file = io.BytesIO()
    with zipfile.ZipFile(
        ram_file, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=0
    ) as zip_file:
        for info, data in zip_infos:
            zip_file.writestr(info, data)

    logging.debug("Writing zip to disk.")
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_bytes(ram_file.getvalue())


def create_manifest(args: argparse.Namespace) -> None:
    """Create json manifest of runfiles.

    Args:
        args: Parsed command line arguments.
    """
    logging.debug("Processing runfiles paths.")
    runfiles = {}
    for pair in args.src_pairs:
        for src, dest in pair:
            runfiles[src] = dest

    logging.debug("Writing manifest to disk.")
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(runfiles, indent=4) + "\n", encoding="utf-8")


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    if "RULES_VENV_RUNFILES_DEBUG" in os.environ or "RULES_VENV_DEBUG" in os.environ:
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            level=logging.DEBUG,
        )

    if args.output.name.endswith(".zip"):
        create_zip(args)
    elif args.output.name.endswith(".json"):
        create_manifest(args)
    else:
        raise ValueError("Output files must be either zip or json files.")

    logging.debug("Done!")


if __name__ == "__main__":
    main()
