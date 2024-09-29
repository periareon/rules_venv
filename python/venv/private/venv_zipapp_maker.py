"""A tool for repackaging Bazel `python_zip_file` files to standard python zipapps."""

import argparse
import json
import logging
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

RlocationPath = str


def _srcs_pair_arg_file(arg: str) -> Tuple[Path, RlocationPath]:
    """Parse a command line argument into a pairing of file paths to rlocationpath."""
    if arg.startswith("'") and arg.endswith("'"):
        arg = arg[1:-1]
    src, _, dest = arg.partition("=")
    if not src or not dest:
        raise ValueError(f"Unexpected src pair: {arg}")
    return Path(src), dest


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--rfile",
        dest="runfile_pairs",
        type=_srcs_pair_arg_file,
        action="append",
        default=[],
        required=True,
        help="A `py_binary`'s `python_zip_file` output group",
    )
    parser.add_argument(
        "--venv_config_info",
        type=json.loads,
        required=True,
        help="Configuration info about the venv being created.",
    )
    parser.add_argument(
        "--zipapp_main_template",
        type=Path,
        required=True,
        help="The path to a template file which represents the zipapp entrypoint.",
    )
    parser.add_argument(
        "--main",
        type=RlocationPath,
        required=True,
        help="The main entrypoint for the zipped python binary.",
    )
    parser.add_argument(
        "--py_runtime",
        type=RlocationPath,
        required=True,
        help="The python interpreter to use.",
    )
    parser.add_argument(
        "--venv_process_wrapper",
        type=RlocationPath,
        required=True,
        help="The rules_venv binary process wrapper.",
    )
    parser.add_argument(
        "--shebang",
        type=str,
        help="The shebang to use for the python entrypoint",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="The output path for the zipapp"
    )

    return parser.parse_args(args)


def install_runfiles(
    pairs: List[Tuple[Path, Path]], venv_config_info: Dict[str, Any], runfiles_dir: Path
) -> RlocationPath:
    """Create a runfiles directory for creating zipapps.

    Args:
        pairs: Pairs of runfile paths to their `rlocationpath` values.
        venv_config_info: Configuration info needed to construct a venv for the given runfiles.
        runfiles_dir: The output location to write into.

    Returns:
        The `rlocationpath` of the config file used to create venvs.
    """
    for src, dest in pairs:
        abs_dest = runfiles_dir / dest
        abs_dest.parent.mkdir(exist_ok=True, parents=True)

        # Copy2 will retain permissions
        shutil.copy2(src, abs_dest)

    config_file = runfiles_dir / f"{venv_config_info['name']}.venv_config.json"
    config_file.write_text(
        json.dumps(venv_config_info, indent=4) + "\n", encoding="utf-8"
    )

    return config_file.name


# pylint: disable-next=too-many-arguments
def write_entrypoint(
    *,
    template: Path,
    py_runtime: RlocationPath,
    venv_process_wrapper: RlocationPath,
    venv_config: RlocationPath,
    main_bin: RlocationPath,
    zipapp_dir: Path,
) -> None:
    """Generate the zipapp entrypoint

    Args:
        template: The path to the template file for the zipapp entrypoint.
        py_runtime: The python interpreter.
        venv_process_wrapper: The venv process wrapper
        venv_config: The venv config file
        main_bin: The main entrypoint.
        zipapp_dir: The directory in which to write outputs.
    """
    content = template.read_text(encoding="utf-8")
    content = content.replace('PY_RUNTIME = ""', f'PY_RUNTIME = "{py_runtime}"')
    content = content.replace(
        'VENV_PROCESS_WRAPPER = ""', f'VENV_PROCESS_WRAPPER = "{venv_process_wrapper}"'
    )
    content = content.replace('VENV_CONFIG = ""', f'VENV_CONFIG = "{venv_config}"')
    content = content.replace('MAIN = ""', f'MAIN = "{main_bin}"')

    # The existence of this file will force the zipapp to use this as the
    # main entrypoint.
    zipapp_main = zipapp_dir / "__main__.py"
    zipapp_main.write_text(content, encoding="utf-8")


def make_zipapp(output: Path, zipapp_dir: Path, shebang: Optional[str] = None) -> None:
    """Run a command to generate a zipapp.

    Because `zipapp.create_archive` doesn't handle permissions, the zipapp must
    be manually created.

    Args:
        output: The zipapp destination.
        shebang: The shebang to use for the zipapp
        zipapp_dir: The zipapp contents
    """

    with output.open("wb") as fd:

        if shebang:
            shebang_bytes = b"#!" + shebang.encode("utf-8")
            fd.write(shebang_bytes)
            logging.debug("Writing shebang to zipapp: #!%s", shebang_bytes)

        with zipfile.ZipFile(
            fd,
            "w",
            compression=zipfile.ZIP_STORED,
        ) as z:
            for child in sorted(zipapp_dir.rglob("*")):
                if child.is_dir():
                    arcname = f"{child.relative_to(zipapp_dir).as_posix()}/"
                    data = b""
                else:
                    arcname = child.relative_to(zipapp_dir).as_posix()
                    data = child.read_bytes()

                info = zipfile.ZipInfo(
                    filename=arcname, date_time=(1980, 1, 1, 0, 0, 0)
                )
                info.create_system = 3
                st_mode = child.stat().st_mode
                info.external_attr = st_mode << 16

                logging.debug(
                    "Writing file to zipapp: (%s) %s", stat.filemode(st_mode), arcname
                )
                z.writestr(info, data)


def main() -> None:
    """The main entrypoint"""
    if len(sys.argv) == 2 and sys.argv[1].startswith("@"):
        args = parse_args(
            Path(sys.argv[1][1:]).read_text(encoding="utf-8").splitlines()
        )
    else:
        args = parse_args()

    if (
        "RULES_VENV_ZIPAPP_MAKER_DEBUG" in os.environ
        or "RULES_VENV_DEBUG" in os.environ
    ):
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            level=logging.DEBUG,
        )

    with tempfile.TemporaryDirectory(prefix="bzl-rvza-") as temp_dir:
        runfiles_dir = Path(temp_dir)
        runfiles_dir.mkdir(exist_ok=True, parents=True)

        logging.debug("Installing runfiles to: %s", runfiles_dir)
        config_file = install_runfiles(
            pairs=args.runfile_pairs,
            venv_config_info=args.venv_config_info,
            runfiles_dir=runfiles_dir,
        )

        write_entrypoint(
            template=args.zipapp_main_template,
            py_runtime=args.py_runtime,
            venv_process_wrapper=args.venv_process_wrapper,
            venv_config=config_file,
            main_bin=args.main,
            zipapp_dir=runfiles_dir,
        )

        logging.debug("Creating zipapp: %s", args.output)
        make_zipapp(output=args.output, shebang=args.shebang, zipapp_dir=runfiles_dir)


if __name__ == "__main__":
    main()
