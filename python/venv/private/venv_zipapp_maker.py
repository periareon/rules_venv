"""A tool for repackaging Bazel `python_zip_file` files to standard python zipapps."""

import argparse
import io
import json
import logging
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

RlocationPath = str


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--runfiles_manifest",
        type=Path,
        required=True,
        help="The runfiles manifest for the py binary.",
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
        "--inject_args",
        type=json.loads,
        required=True,
        help="Json encoded arguments to inject into the zipapp.",
    )
    parser.add_argument(
        "--inject_env",
        type=json.loads,
        required=True,
        help="Json encoded environment variables to inject into the zipapp.",
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
    files_manifest: Path, venv_config_info: Dict[str, Any], runfiles_dir: Path
) -> RlocationPath:
    """Create a runfiles directory for creating zipapps.

    Args:
        files_manifest: The manifest of files to install.
        venv_config_info: Configuration info needed to construct a venv for the given runfiles.
        runfiles_dir: The output location to write into.

    Returns:
        The `rlocationpath` of the config file used to create venvs.
    """
    with files_manifest.open("r", encoding="utf-8") as manifest_file:
        for line in manifest_file:
            rlocation, _, real_path = line.strip().partition(" ")

            # Ensure spaces are expanded in the zip file. For more details see:
            # https://github.com/bazelbuild/bazel/commit/c9115305cb81e7fe645f91ca790642cab136b2a1
            dest_path = runfiles_dir / rlocation.replace(r"\s", " ")

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(real_path, dest_path)

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
    args: Sequence[str],
    env: Mapping[str, str],
    zipapp_dir: Path,
) -> None:
    """Generate the zipapp entrypoint

    Args:
        template: The path to the template file for the zipapp entrypoint.
        py_runtime: The python interpreter.
        venv_process_wrapper: The venv process wrapper
        venv_config: The venv config file
        main_bin: The main entrypoint.
        args: Arguments to inject before all command line args of the zipapp.
        env: Environment variables to set for all invocations of the zipapp.
        zipapp_dir: The directory in which to write outputs.
    """
    content = template.read_text(encoding="utf-8")
    content = content.replace('PY_RUNTIME = ""', f'PY_RUNTIME = "{py_runtime}"')
    content = content.replace(
        'VENV_PROCESS_WRAPPER = ""', f'VENV_PROCESS_WRAPPER = "{venv_process_wrapper}"'
    )
    content = content.replace('VENV_CONFIG = ""', f'VENV_CONFIG = "{venv_config}"')
    content = content.replace('MAIN = ""', f'MAIN = "{main_bin}"')
    content = content.replace("ARGS: List[str] = []", f"ARGS: List[str] = {args}")
    content = content.replace("ENV: Mapping[str, str] = {}", f"ENV: Mapping[str, str] = {env}")

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

    zip_infos: List[Tuple[zipfile.ZipInfo, bytes]] = []

    for child in sorted(zipapp_dir.rglob("*")):
        if child.is_dir():
            arcname = f"{child.relative_to(zipapp_dir).as_posix()}/"
            data = b""
        else:
            arcname = child.relative_to(zipapp_dir).as_posix()
            data = child.read_bytes()

        info = zipfile.ZipInfo(filename=arcname, date_time=(1980, 1, 1, 0, 0, 0))
        info.create_system = 3
        st_mode = child.stat().st_mode
        info.external_attr = st_mode << 16

        zip_infos.append((info, data))

        logging.debug(
            "Writing file to zipapp: (%s) %s", stat.filemode(st_mode), arcname
        )

    ram_file = io.BytesIO()

    with zipfile.ZipFile(
        ram_file,
        "w",
        zipfile.ZIP_DEFLATED,
        compresslevel=0,
    ) as z:
        for info, data in zip_infos:
            logging.debug(
                "Writing file to zipapp: (%s) %s",
                stat.filemode(info.external_attr >> 16),
                info.filename,
            )
            z.writestr(info, data)

    with output.open("wb") as fd:
        if shebang:
            shebang_bytes = b"#!" + shebang.rstrip().encode("utf-8") + b"\n"
            fd.write(shebang_bytes)
            logging.debug("Writing shebang to zipapp: #!%s", shebang_bytes)

        fd.write(ram_file.getvalue())


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
            files_manifest=args.runfiles_manifest,
            venv_config_info=args.venv_config_info,
            runfiles_dir=runfiles_dir,
        )

        write_entrypoint(
            template=args.zipapp_main_template,
            py_runtime=args.py_runtime,
            venv_process_wrapper=args.venv_process_wrapper,
            venv_config=config_file,
            main_bin=args.main,
            args=args.inject_args,
            env=args.inject_env,
            zipapp_dir=runfiles_dir,
        )

        logging.debug("Creating zipapp: %s", args.output)
        make_zipapp(output=args.output, shebang=args.shebang, zipapp_dir=runfiles_dir)


if __name__ == "__main__":
    main()
