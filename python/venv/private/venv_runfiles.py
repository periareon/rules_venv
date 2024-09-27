"""A tool for building a runfiles zip file for use in environments that don't support runfiles directories

This primarily exists due to the lack of:
https://github.com/bazelbuild/bazel/issues/15486
"""

import argparse
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple


def _srcs_pair_arg_file(arg: str) -> List[Tuple[Path, Path]]:
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
        pairs.append((Path(src), Path(dest)))

    return pairs


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output", type=Path, required=True, help="The path to the output zip file"
    )
    parser.add_argument(
        "--output_venv_config",
        type=Path,
        required=True,
        help="Configuration info about the venv being created.",
    )
    parser.add_argument(
        "--venv_config_data",
        type=json.loads,
        required=True,
        help="Configuration info about the venv being created.",
    )
    parser.add_argument(
        "src_pairs",
        type=_srcs_pair_arg_file,
        help="Source files to include in runfiles.",
    )

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    args.output.parent.mkdir(exist_ok=True, parents=True)

    pairs_to_zip = []
    external_repo_files = defaultdict(list)
    repos_with_generated_files = set()
    for src, dest in args.src_pairs:
        is_generated = False
        if src.parts[0] == "external":
            repo_name = src.parts[1]
        elif src.parts[0] == "bazel-out":
            is_generated = True
            if src.parts[2] == "external":
                repo_name = src.parts[3]
            else:
                repo_name = "_main"
        else:
            repo_name = "_main"

        if is_generated:
            repos_with_generated_files.add(repo_name)
        external_repo_files[repo_name].append((src, dest))

    for repo in sorted(repos_with_generated_files):
        pairs_to_zip.extend(external_repo_files[repo])

    static_repos = sorted(set(external_repo_files) - repos_with_generated_files)

    config_data = dict(args.venv_config_data)
    config_data["static_repos"] = static_repos
    args.output_venv_config.write_text(
        json.dumps(config_data, indent=4) + "\n", encoding="utf-8"
    )

    with zipfile.ZipFile(str(args.output), "w") as zip_file:
        for src, dest in pairs_to_zip:
            if "bazel-out" not in str(src):
                print("Copying: {}".format(src))
            # Ensure timestamps are ignored so outputs are reproducible.
            info = zipfile.ZipInfo(filename=str(dest), date_time=(1980, 1, 1, 0, 0, 0))

            with src.open("rb") as f:
                zip_file.writestr(info, f.read())


if __name__ == "__main__":
    main()
