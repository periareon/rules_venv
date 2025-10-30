"""`PyPex` process wrapper."""

import argparse
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional, Sequence

RLocationPath = str


def _srcs_pair_arg_file(arg: str) -> tuple[RLocationPath, Path]:
    """Parse a command line argument into a pairing of file paths to rlocationpath."""
    if arg.startswith("'") and arg.endswith("'"):
        arg = arg[1:-1]
    rlocation, _, execpath = arg.partition("=")
    if not rlocation or not execpath:
        raise ValueError(f"Unexpected src pair: {arg}")
    return rlocation, Path(execpath)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="The output file.",
    )
    parser.add_argument(
        "--main",
        type=RLocationPath,
        required=True,
        help="The main entrypoint for the binary.",
    )
    parser.add_argument(
        "--runfiles_manifest",
        type=Path,
        required=True,
        help="The runfiles manifest of the binary to build.",
    )
    parser.add_argument(
        "--import",
        dest="imports",
        type=str,
        default=[],
        action="append",
        help="Import paths required by the binary.",
    )
    parser.add_argument(
        "--pex_import",
        dest="pex_imports",
        type=str,
        default=[],
        action="append",
        help="Import paths required by the pex.",
    )
    parser.add_argument(
        "--pex_src",
        dest="pex_srcs",
        type=_srcs_pair_arg_file,
        default=[],
        required=True,
        action="append",
        help="Pex source files.",
    )
    parser.add_argument(
        "--cpus", type=int, required=True, help="The number of cores to use"
    )
    parser.add_argument(
        "--scie",
        default=False,
        action="store_true",
        help="Whether or not to produce a scie binary.",
    )
    parser.add_argument(
        "--scie_platform",
        type=str,
        help="An optional platform arg to pass to pex. `--scie` must also be passed.",
    )
    parser.add_argument(
        "--scie_science",
        type=Path,
        help="The scie science binary to use for scie targets.",
    )

    if len(sys.argv) == 2 and sys.argv[1].startswith("@"):
        argv = Path(sys.argv[1][1:]).read_text(encoding="utf-8").splitlines()
        args = parser.parse_args(argv)
    else:
        args = parser.parse_args()

    if args.scie_platform and not args.scie:
        parser.error("`--platform` requires `--scie` to be passed.")

    return args


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
            pth: The `pth` values to add to PYTHONPATH.
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

        pth_data = []
        for pth in self.bazel_pth:
            pth_data.append(str(Path(pth)))

        pth_file = site_packages / "bazel.pth"
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


def get_install_fn() -> Callable[[Path, Path], None]:
    """Compute the installer function for runfiles directories appropriate for the platform."""

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

    return install_fn


def install_files(
    imports: list[str], runfiles_manifest: Path, output_dir: Path
) -> None:
    """A helper for installing files in a directory.

    Args:
        imports: A list of paths to extract from `runfiles_mainfest`.
        runfiles_manifest: The RUNFILES_MANIFEST_FILE of the binary to build the pex for.
        output_dir: The output directory in which to install files.
    """

    install_fn = get_install_fn()

    imports_tuple = tuple(imports)

    for line in runfiles_manifest.read_text(encoding="utf-8").splitlines():
        rlocation, _, real_path = line.strip().partition(" ")
        rlocation = rlocation.replace("\\s", " ")

        if rlocation.startswith(imports_tuple):
            abs_src = Path(real_path)
            abs_dest = output_dir / rlocation
            abs_dest.parent.mkdir(exist_ok=True, parents=True)
            install_fn(abs_src.absolute(), abs_dest)


def install_pex(srcs: list[tuple[RLocationPath, Path]], runfiles_dir: Path) -> None:
    """Install additional pex sources into a runfiles directory."""
    install_fn = get_install_fn()

    for rlocation, execpath in srcs:
        abs_dest = runfiles_dir / rlocation
        abs_dest.parent.mkdir(exist_ok=True, parents=True)
        install_fn(execpath.absolute(), abs_dest)


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    is_debug = (
        "RULES_VENV_PEX_PROCESS_WRAPPER_DEBUG" in os.environ
        or "RULES_VENV_DEBUG" in os.environ
    )

    if is_debug:
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            level=logging.DEBUG,
        )

    # The new venv is only a couple of files and directories, cleaning
    # it up should be fast so it's written to a temp directory.
    with tempfile.TemporaryDirectory(
        prefix="bzl-pex-", ignore_cleanup_errors=True
    ) as tmp:
        temp_dir = Path(tmp)

        runfiles_dir = temp_dir / "runfiles"
        logging.debug("Creating runfiles dir at: %s", runfiles_dir)
        install_files(
            imports=args.imports,
            output_dir=runfiles_dir,
            runfiles_manifest=args.runfiles_manifest,
        )

        logging.debug("Creating pex to: %s", runfiles_dir)
        install_pex(args.pex_srcs, runfiles_dir)

        venv_dir = temp_dir / "venv"
        venv_dir.mkdir(exist_ok=True, parents=True)

        # Collect combined pth values.
        pth = [f"{runfiles_dir}/{i}" for i in args.imports]
        pth.extend(
            [
                f"{runfiles_dir}/{i}"
                for i in [i for i in args.pex_imports if i not in args.imports]
            ]
        )

        logging.debug("Creating venv at: %s", venv_dir)
        venv_interpreter = create_venv(
            venv_name="bzl-pex-builder",
            venv_dir=venv_dir,
            pth=pth,
        )
        logging.debug("Created venv with interpreter: %s", venv_interpreter)

        pex_root = temp_dir / "pex_root"
        pex_root.mkdir(exist_ok=True, parents=True)

        # Build pex command with hermetic settings
        # Use venv interpreter for pex execution to ensure compatibility
        pex_cmd = [
            str(venv_interpreter),
            "-m",
            "pex",
            "--output",
            str(args.output),
            "--python-script",
            str(runfiles_dir / args.main),
            "--venv-repository",
            str(venv_dir),
            "--no-index",  # Don't use PyPI, only use venv packages
            "--sh-boot",
            "--jobs",
            str(args.cpus),
            "--no-use-system-time",
            "--no-compile",
            "--layout",
            "zipapp",
            "--pex-root",
            str(pex_root),
        ]

        if args.scie:
            pex_cmd.extend(
                [
                    "--scie-only",
                    "--scie",
                    "eager",
                    "--scie-science-binary",
                    str(args.scie_science),
                    "--scie-platform",
                    args.scie_platform,
                ]
            )

        # Ensure all normal imports are added
        for path in args.imports:
            pex_cmd.extend(["--sources-directory", str(runfiles_dir / path)])

        if is_debug:
            pex_cmd.append("-vvv")

        env = dict(os.environ)
        env["PEX_ROOT"] = str(pex_root)

        logging.debug("Running pex command: %s", " ".join(pex_cmd))
        result = subprocess.run(
            pex_cmd,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            check=False,
            env=env,
        )

        if result.returncode != 0:
            print(result.stdout.decode("utf-8"), file=sys.stderr)
            sys.exit(result.returncode)

        if is_debug:
            print(result.stdout.decode("utf-8"), file=sys.stderr)

        # If the file extension ends in `.pex` a `pex` will always be created but at
        # at the output location but we should instead move the real pex (which will omit
        # the `.pex` extension) to what Bazel expects the output to be.
        if args.scie and args.output.name.endswith(".pex"):
            scie_output = args.output.parent / args.output.name[: -len(".pex")]
            logging.debug(
                "Replacing pex output with scie: `%s` -> `%s`", scie_output, args.output
            )
            if args.output.exists():
                args.output.unlink()
            shutil.copy2(scie_output, args.output)

        logging.debug("Successfully created pex file: %s", args.output)


if __name__ == "__main__":
    main()
