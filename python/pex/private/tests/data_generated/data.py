"""A test script that reads a file using runfiles API and writes to output."""

import argparse
import os
import platform
from pathlib import Path

from python.runfiles import Runfiles


def _find_runfiles() -> Runfiles:
    """Locate Bazel runfiles.

    Note: Pex will replace argv0 but assign the pex file to the `PEX`
        environment variable. This should be used to update `argv0`
        so runfiles are locatable.
    """
    env = dict(os.environ)
    if (
        "RUNFILES_DIR" not in env or "RUNFILES_MANIFEST_FILE" not in env
    ) and "PEX" in env:
        pex = Path(env["PEX"])
        runfiles_dir = env.get("RUNFILES_DIR")
        runfiles_manifest_file = env.get("RUNFILES_MANIFEST_FILE")
        if not runfiles_dir:
            r_dir = pex.parent / f"{pex.name}.runfiles"
            if r_dir.exists():
                runfiles_dir = str(r_dir)

            manifest = r_dir / "MANIFEST"
            if not runfiles_manifest_file and manifest.exists():
                runfiles_manifest_file = str(manifest)

        if "RUNFILES_MANIFEST_FILE" not in env:
            manifest = pex.parent / f"{pex.name}.runfiles_manifest"
            if manifest.exists():
                runfiles_manifest_file = str(manifest)

        if runfiles_dir:
            env["RUNFILES_DIR"] = runfiles_dir
        if runfiles_manifest_file:
            env["RUNFILES_MANIFEST_FILE"] = runfiles_manifest_file

    runfiles = Runfiles.Create(env)
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles.")

    return runfiles


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runfile.
    """
    # TODO: https://github.com/periareon/rules_venv/issues/37
    source_repo = None
    if platform.system() == "Windows":
        source_repo = ""
    runfile = runfiles.Rlocation(rlocationpath, source_repo)
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


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

    # Create runfiles object
    runfiles = _find_runfiles()

    # Read the data file using runfiles API
    rlocationpath = "_main/python/pex/private/tests/data_generated/data_file.txt"
    data_file = _rlocation(runfiles, rlocationpath)

    # Read the content and write to output
    content = data_file.read_bytes()
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_bytes(content)


if __name__ == "__main__":
    main()
