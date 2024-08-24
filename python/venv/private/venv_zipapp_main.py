"""The template entrypoint for rules_venv zipapps.

This should effectively be a python implementation of `@rules_venv//python/venv/private:entrypoint.sh`
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Template variables
PY_RUNTIME = ""
VENV_PROCESS_WRAPPER = ""
VENV_CONFIG = ""
MAIN = ""


def extract_zip(zip_file: Path, output_dir: Path) -> None:
    """A helper for extracting a zip file and maintaining file permissions

    Args:
        zip_file (Path): The zip file to extract
        output_dir (Path): The output location
    """
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        for info in zip_ref.infolist():
            extracted_path = zip_ref.extract(info, output_dir)

            zip_unix_system = 3
            if info.create_system == zip_unix_system:
                unix_attributes = info.external_attr >> 16
                if unix_attributes:
                    os.chmod(extracted_path, unix_attributes)


def main() -> None:
    """The main entrypoint."""

    if "RULES_VENV_ZIPAPP_DEBUG" in os.environ:
        logging.basicConfig(level=logging.DEBUG)

    assert PY_RUNTIME, "Failed to resolve template. PY_RUNTIME"
    assert VENV_PROCESS_WRAPPER, "Failed to resolve template. VENV_PROCESS_WRAPPER"
    assert VENV_CONFIG, "Failed to resolve template. VENV_CONFIG"
    assert MAIN, "Failed to resolve template. MAIN"

    runfiles_dir = Path(
        tempfile.mkdtemp(prefix="bzl-rvz-", dir=os.getenv("TEST_TMPDIR"))
    )
    try:
        runfiles_dir.mkdir(exist_ok=True, parents=True)
        logging.debug("Extracting runfiles to: %s", runfiles_dir)
        extract_zip(zip_file=Path(__file__).parent, output_dir=runfiles_dir)
        os.environ["RUNFILES_DIR"] = str(runfiles_dir)

        args = [
            str(runfiles_dir / PY_RUNTIME),
            str(runfiles_dir / VENV_PROCESS_WRAPPER),
            str(runfiles_dir / VENV_CONFIG),
            str(runfiles_dir / MAIN),
        ] + sys.argv[1:]

        logging.debug("Spawning subprocess: %s", " ".join(args))
        result = subprocess.run(
            args,
            check=False,
            capture_output=False,
        )
        sys.exit(result.returncode)

    finally:
        if "TEST_TMPDIR" not in os.environ:
            try:
                shutil.rmtree(runfiles_dir)
            except (PermissionError, OSError) as exc:
                logging.warning(
                    "Error encountered while cleaning up runfiles %s: %s",
                    runfiles_dir,
                    exc,
                )


if __name__ == "__main__":
    main()
