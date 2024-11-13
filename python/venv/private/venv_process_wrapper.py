"""The `rules_venv` process wrapper for all executables.

This script is responsible for building a venv and running the
main entrypoint provided by the Bazel rule.
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import List, NamedTuple, Optional, Sequence


class ParsedArgs(NamedTuple):
    """A fast alternative to `argparse.Namespace`."""

    venv_config: Path
    """The path to the rules_venv config file for the current target."""

    main: Path
    """The target's entrypoint."""

    main_args: Sequence[str]
    """Arguments to pass to `main`."""


def parse_args() -> ParsedArgs:
    """Parse command line arguments."""

    return ParsedArgs(
        venv_config=Path(sys.argv[1]),
        main=Path(sys.argv[2]),
        main_args=sys.argv[3:],
    )


class ExtendedEnvBuilder(venv.EnvBuilder):
    """https://docs.python.org/3/library/venv.html"""

    def __init__(
        self,
        name: str,
        pth: Sequence[str],
    ):
        """Constructor.

        Args:
            name: The name of the venv (prompt).
            pth: The `pth` values to add to PYTHONPATH. Note that each value
                can contain a format string `{runfiles_dir}` that will be
                substituted out.
        """
        self.bazel_pth = pth
        self.interpreter: Optional[Path] = None

        super().__init__(
            system_site_packages=False,
            clear=False,
            upgrade=False,
            with_pip=False,
            symlinks=True,
            prompt=name,
            upgrade_deps=False,
        )

    def post_setup(self, context: SimpleNamespace) -> None:
        """
        Set up any packages which need to be pre-installed into the
        virtual environment being created.

        https://docs.python.org/3/library/site.html

        Args:
            context: The information for the virtual environment
                creation request being processed.
        """
        self.interpreter = Path(context.env_exe)

        major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
        if platform.system() == "Windows":
            site_packages = Path(context.env_dir) / "Lib/site-packages"
        else:
            site_packages = (
                Path(context.env_dir) / f"lib/python{major_minor}/site-packages"
            )

        if not site_packages:
            raise FileNotFoundError(
                f"Failed to find site-packages directory at {site_packages}"
            )

        if "PY_VENV_RUNFILES_DIR" in os.environ:
            runfiles_path = Path(os.environ["PY_VENV_RUNFILES_DIR"])
        else:
            runfiles_path = Path(os.environ["RUNFILES_DIR"])

        if not runfiles_path.is_absolute():
            runfiles_path = Path.cwd() / runfiles_path

        pth_data = []
        for pth in self.bazel_pth:
            abs_pth = Path(pth.format(runfiles_dir=runfiles_path))
            pth_data.append(str(abs_pth))

        pth_file = site_packages / "rules_venv.pth"
        pth_file.write_text(
            "\n".join(pth_data) + "\n",
            encoding="utf-8",
        )


def create_venv(
    venv_name: str,
    venv_dir: Path | str,
    pth: Sequence[str],
) -> Path:
    """Construct a new Python venv at the requested location.

    Args:
        venv_name: The name (prompt) of the venv.
        venv_dir: The location where the venv should be created
        pth: Values to add to the a `pth` file for import resolution.

    Returns:
        The path to the new venv interpreter.
    """
    builder = ExtendedEnvBuilder(
        name=venv_name,
        pth=pth,
    )

    builder.create(venv_dir)

    interpreter = builder.interpreter
    if not interpreter:
        raise RuntimeError("Failed to locate venv interpreter")

    return interpreter


def extract_zip(zip_file: Path, output_dir: Path) -> None:
    """A helper for extracting a zip file and maintaining file permissions

    Args:
        zip_file: The zip file to extract
        output_dir: The output location
    """
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        for info in zip_ref.infolist():
            extracted_path = zip_ref.extract(info, output_dir)

            zip_unix_system = 3
            if info.create_system == zip_unix_system:
                unix_attributes = info.external_attr >> 16
                if unix_attributes:
                    os.chmod(extracted_path, unix_attributes)


def install_files(
    manifest: Path, output_dir: Path, src_root: Optional[Path] = None
) -> None:
    """A helper for installing files in a directory.

    Args:
        manifest: The manifest to use for installing files. Expected to be a json
            encoded map of source paths to rlocationpaths
        output_dir: The output directory in which to install files.
        src_root: The root from which all source files in `manifest` are relative to.
    """

    def link(src: Path, dest: Path) -> None:
        """Symlink `dest` to `src`."""
        dest.symlink_to(src)

    def copy(src: Path, dest: Path) -> None:
        """Copy `src` to `dest`."""
        shutil.copy2(src, dest)

    install_fn = link

    # Using symlinks on windows is both not guaranteed and can have
    # significant performance impacts at runtime. Some profiling
    # observed the time it takes to copy files is over all less than
    # the time lost in runtime with symlinks.
    if platform.system() == "Windows":
        install_fn = copy

    pairs = json.loads(manifest.read_text(encoding="utf-8"))

    if "RUNFILES_MANIFEST_FILE" in os.environ:
        runfiles = {}
        for line in (
            Path(os.environ["RUNFILES_MANIFEST_FILE"])
            .read_text(encoding="utf-8")
            .splitlines()
        ):
            rlocation, _, real_path = line.partition(" ")
            runfiles[rlocation] = real_path

        for dest in pairs.values():
            abs_src = Path(runfiles[dest])
            abs_dest = output_dir / dest
            abs_dest.parent.mkdir(exist_ok=True, parents=True)
            install_fn(abs_src, abs_dest)

    else:
        if src_root is None:
            src_root = Path.cwd()

        for src, dest in pairs.items():
            abs_src = src_root / src
            abs_dest = output_dir / dest
            abs_dest.parent.mkdir(exist_ok=True, parents=True)
            install_fn(abs_src, abs_dest)


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    if (
        "RULES_VENV_PROCESS_WRAPPER_DEBUG" in os.environ
        or "RULES_VENV_DEBUG" in os.environ
    ):
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            level=logging.DEBUG,
        )

    config = json.loads(args.venv_config.read_text(encoding="utf-8"))

    # The new venv is only a couple of files and directories, cleaning
    # it up should be fast so it's written to a temp directory.
    temp_dir = Path(
        tempfile.mkdtemp(
            prefix=f"venv-{config['name']}-",
            dir=os.getenv("TEST_TMPDIR"),
        )
    )

    venv_dir = temp_dir / "venv"
    venv_dir.mkdir(exist_ok=True, parents=True)

    # If a runfiles collection was passed, always use it in place of any
    # pre-defined runfiles directories.
    if "VENV_RUNFILES_COLLECTION" in os.environ:
        runfiles_dir = temp_dir / "runfiles"
        runfiles_dir.mkdir(exist_ok=True, parents=True)
        os.environ["PY_VENV_RUNFILES_DIR"] = str(runfiles_dir)

        runfiles_collection = os.environ["VENV_RUNFILES_COLLECTION"]
        if runfiles_collection.endswith(".zip"):
            logging.debug("Extracting runfiles collection to: %s", runfiles_dir)
            runfiles_dir.mkdir(exist_ok=True, parents=True)
            extract_zip(
                zip_file=Path(runfiles_collection),
                output_dir=runfiles_dir,
            )
        elif runfiles_collection.endswith(".json"):
            logging.debug("Linking runfiles collection to: %s", runfiles_dir)
            install_files(manifest=Path(runfiles_collection), output_dir=runfiles_dir)
        else:
            raise EnvironmentError(
                f"Unexpected `VENV_RUNFILES_COLLECTION` value: {runfiles_collection}"
            )

        logging.debug("Runfiles ready!")

    # The venv dir is only cleaned up if the target is not running under
    # a Bazel test. Bazel will clean up the directory for us when the test
    # finishes.
    try:
        # Create a new venv.
        logging.debug("Creating venv at: %s", venv_dir)
        venv_interpreter = create_venv(
            venv_name=config["label"],
            venv_dir=venv_dir,
            pth=config["pth"],
        )

        # Subprocess the entrypoint via the new venv.
        main_args: List[str] = [
            str(venv_interpreter),
            "-B",  # don't write .pyc files on import; also PYTHONDONTWRITEBYTECODE=x
            "-s",  # don't add user site directory to sys.path; also PYTHONNOUSERSITE
        ]
        if (
            sys.version_info.major >= 3 and sys.version_info.minor >= 11
        ) or sys.version_info.major > 3:
            main_args.append("-P")  # safe paths (available in Python 3.11)
        main_args.append(str(args.main))
        main_args.extend(args.main_args)

        logging.debug("Spawning subprocess: %s", " ".join(main_args))
        result = subprocess.run(main_args, check=False, capture_output=False)
        logging.debug("Process complete with exit code: %d", result.returncode)
        sys.exit(result.returncode)
    finally:
        # https://bazel.build/reference/test-encyclopedia#initial-conditions
        # TEST_TMPDIR: Is defined whenever running in under `bazel test`.
        if "TEST_TMPDIR" not in os.environ:
            try:
                shutil.rmtree(temp_dir)
            except (PermissionError, OSError) as exc:
                logging.warning(
                    "Error encountered while cleaning up venv %s: %s", temp_dir, exc
                )


if __name__ == "__main__":
    main()
