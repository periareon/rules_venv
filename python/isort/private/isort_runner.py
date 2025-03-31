"""The process wrapper for isort aspects."""

import argparse
import configparser
import contextlib
import io
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Generator, List, Optional, Sequence

from python.runfiles import Runfiles  # type: ignore

# isort gets confused seeing itself in a file, explicitly skip sorting this
# isort: off
from isort.main import main as isort_main


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
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


def _maybe_runfile(arg: str) -> Path:
    """Parse an argument into a path while resolving runfiles.

    Not all contexts this script runs in will use runfiles. In
    these cases the functon is a noop.
    """
    if "BAZEL_TEST" not in os.environ:
        return Path(arg)

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles")
    return _rlocation(runfiles, arg)


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments

    Returns:
        A struct of parsed arguments.
    """
    parser = argparse.ArgumentParser("isort process wrapper")

    parser.add_argument(
        "--marker",
        type=Path,
        help="The file to create as an indication that the 'PyISortFormatCheck' action succeeded.",
    )
    parser.add_argument(
        "--src",
        dest="sources",
        action="append",
        type=_maybe_runfile,
        required=True,
        help="The source file to perform formatting on.",
    )
    parser.add_argument(
        "--import",
        dest="imports",
        action="append",
        default=[],
        type=Path,
        help="Import paths for first party directories.",
    )
    parser.add_argument(
        "--settings-path",
        type=_maybe_runfile,
        required=True,
        help="The path to an isort config file.",
    )
    parser.add_argument(
        "isort_args",
        nargs="*",
        help="Remaining arguments to forward to isort.",
    )

    return parser.parse_args(args)


def locate_first_party_src_paths(
    runfiles_dir: Path, imports: Sequence[str]
) -> List[str]:
    """Determine the list of first party packages.

    Args:
        runfiles_dir: The path to fully formed runfiles.
        imports: The runfiles import paths.

    Returns:
        The names of top level modules in the given root.
    """

    return [str(runfiles_dir / path) for path in imports]


def generate_config_with_projects(
    existing: Path, output: Path, src_paths: List[str]
) -> None:
    """Write a new config file with first party imports merged into it.

    Args:
        existing: The location of an existing config file
        output: The output location for the new config file.
        src_paths: A list of directories to consider source paths
    """
    cfg_pairs = [
        (".isort.cfg", "settings"),
        (".cfg", "isort"),
        (".ini", "isort"),
        ("pyproject.toml", "tool.isort"),
    ]
    for suffix, section in cfg_pairs:
        if not existing.name.endswith(suffix):
            continue

        if suffix.endswith(".toml"):
            raise NotImplementedError("There is no writer for tomllib")

        config = configparser.ConfigParser()
        config.read(str(existing))

        if section not in config.sections():
            config.add_section(section)

        known_src_paths = config.get(section, "src_paths", fallback="")

        config.set(
            section,
            "src_paths",
            ",".join(
                pkg
                for pkg in sorted(set(src_paths + known_src_paths.split(",")))
                if pkg
            ),
        )

        with output.open("w", encoding="utf-8") as fhd:
            config.write(fhd)

        return

    raise ValueError(f"Unexpected isort config file '{existing}'.")


def _no_realpath(path, **kwargs):  # type: ignore
    """Avoid resolving symlinks and instead, simply convert paths to absolute."""
    del kwargs
    return os.path.abspath(path)


@contextlib.contextmanager
def determinisim_patch() -> Generator[None, None, None]:
    """A context manager for applying deterministic behavior to the python stdlib."""

    # Avoid sandbox escapes
    old_realpath = os.path.realpath
    os.path.realpath = _no_realpath  # type: ignore

    try:
        yield
    finally:
        os.path.realpath = old_realpath


def _load_args() -> Sequence[str]:
    """Load command line arguments from the environment."""
    if "BAZEL_TEST" in os.environ and "PY_ISORT_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["PY_ISORT_RUNNER_ARGS_FILE"])
        return arg_file.read_text(encoding="utf-8").splitlines()

    return sys.argv[1:]


def _get_runfiles_dir() -> Path:
    """Locate the runfiles directory from the environment."""
    # Determined by rules_venv
    if "PY_VENV_RUNFILES_DIR" in os.environ:
        return Path(os.environ["PY_VENV_RUNFILES_DIR"])
    if "RUNFILES_DIR" in os.environ:
        return Path(os.environ["RUNFILES_DIR"])

    raise EnvironmentError("Unable to locate runfiles directory.")


def main() -> None:
    """The main entrypoint."""
    args = parse_args(_load_args())

    runfiles_dir = _get_runfiles_dir()
    imports = locate_first_party_src_paths(runfiles_dir, args.imports)

    old_stderr = sys.stderr
    old_stdout = sys.stdout

    stream = io.StringIO()
    if args.marker:
        sys.stderr = stream
        sys.stdout = stream

    exit_code = 0
    temp_dir = tempfile.mkdtemp(prefix="bazel_isort-", dir=os.getenv("TEST_TMPDIR"))
    try:
        os.environ["HOME"] = str(temp_dir)
        os.environ["USERPROFILE"] = str(temp_dir)

        settings_path = Path(temp_dir) / args.settings_path.name
        generate_config_with_projects(args.settings_path, settings_path, imports)

        isort_args = ["--settings-path", str(settings_path)]

        if "RULES_VENV_ISORT_DEBUG" in os.environ:
            isort_args.append("--verbose")
            settings_content = settings_path.read_text(encoding="utf-8")
            print(
                f"isort config:\n```\n{settings_content}\n```",
                file=sys.stderr,
            )

        isort_args.extend(args.isort_args + [str(src) for src in args.sources])

        with determinisim_patch():
            isort_main(isort_args)

    except SystemExit as exc:
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, str):
            exit_code = int(exc.code)
        else:
            exit_code = exc.code

    finally:
        if args.marker:
            sys.stderr = old_stderr
            sys.stdout = old_stdout

        if (
            "TEST_TMPDIR" not in os.environ
            and "RULES_VENV_ISORT_DEBUG" not in os.environ
        ):
            shutil.rmtree(temp_dir)

    if args.marker:
        if exit_code == 0:
            args.marker.write_bytes(b"")
        else:
            print(stream.getvalue(), file=sys.stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
