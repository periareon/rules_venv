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
import tomllib
from collections.abc import Generator, Iterable, Sequence
from pathlib import Path
from typing import Any, cast

from python.runfiles import Runfiles
from rules_venv_vendor import tomli_w

# isort gets confused seeing itself in a file, explicitly skip sorting this
# isort: off
from isort.main import main as isort_main
from isort.settings import CONFIG_SECTIONS, FALLBACK_CONFIG_SECTIONS


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


def _maybe_runfile(arg: str) -> Path:
    """Parse an argument into a path while resolving runfiles.

    Not all contexts this script runs in will use runfiles. In
    these cases the functon is a noop.
    """
    if "BAZEL_TEST" not in os.environ:
        return Path(arg)

    runfiles = Runfiles.Create()
    if not runfiles:
        raise OSError("Failed to locate runfiles")
    return _rlocation(runfiles, arg)


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
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
) -> list[str]:
    """Determine the list of first party packages.

    Args:
        runfiles_dir: The path to fully formed runfiles.
        imports: The runfiles import paths.

    Returns:
        The names of top level modules in the given root.
    """

    return [str(runfiles_dir / path) for path in imports]


# The INI-flavored suffixes isort reads. Which sections it reads out of
# such a file is `_config_sections`, not a second table here.
_INI_SUFFIXES = (".cfg", ".ini")


def _config_sections(existing: Path) -> Sequence[str]:
    """Find the sections isort keeps a config file's settings in.

    Taken from isort rather than restated here, so that a release which
    teaches it a new name teaches this at the same time.
    `CONFIG_SECTIONS` is keyed by file name and `FALLBACK_CONFIG_SECTIONS`
    covers every name not in it, which is the lookup
    `isort.settings.Config` itself performs.

    Args:
        existing: The location of an existing config file.

    Returns:
        The sections isort would read, in the order it reads them.
    """
    return CONFIG_SECTIONS.get(existing.name, FALLBACK_CONFIG_SECTIONS)


def _merge_src_paths(known: Iterable[Any], src_paths: Sequence[str]) -> list[str]:
    """Combine the config's own source paths with Bazel's.

    Args:
        known: The source paths the user's config already declares.
        src_paths: The first party directories Bazel knows about.

    Returns:
        The two sets as one, sorted so that the same inputs give the
        same config file.
    """
    combined = set(src_paths)
    combined.update(str(path).strip() for path in known)
    return sorted(path for path in combined if path)


def _generate_ini_config(existing: Path, output: Path, src_paths: list[str]) -> None:
    """Write an INI config with first party imports merged into it."""
    section = _config_sections(existing)[0]

    config = configparser.ConfigParser()
    config.read(str(existing))

    if section not in config.sections():
        config.add_section(section)

    known_src_paths = config.get(section, "src_paths", fallback="")

    config.set(
        section,
        "src_paths",
        ",".join(_merge_src_paths(known_src_paths.split(","), src_paths)),
    )

    with output.open("w", encoding="utf-8") as fhd:
        config.write(fhd)


def _generate_toml_config(existing: Path, output: Path, src_paths: list[str]) -> None:
    """Write a TOML config with first party imports merged into it.

    Only isort's own settings are carried across. The rest of a
    `pyproject.toml` -- the build system, the other tools' tables -- is
    nothing isort reads, and leaving it out keeps the generated file to
    the one table this has to be able to write back out.

    isort reads a TOML config's settings out of whichever sections its
    file name calls for, so the sections are read the way isort would
    read them and written back under the one name every lookup finds.
    """
    with existing.open("rb") as fhd:
        data = tomllib.load(fhd)

    settings: dict[str, Any] = {}
    for section in _config_sections(existing):
        found: Any = data
        for key in section.split("."):
            found = found.get(key, {}) if isinstance(found, dict) else {}
        settings.update(found)

    settings["src_paths"] = _merge_src_paths(settings.get("src_paths", []), src_paths)

    # `tool.isort` whatever the settings were read out of, that being the
    # one name every lookup above ends at.
    output.write_text(tomli_w.dumps({"tool": {"isort": settings}}), encoding="utf-8")


def generate_config_with_projects(
    existing: Path, output: Path, src_paths: list[str]
) -> None:
    """Write a new config file with first party imports merged into it.

    The copy is written in the format the original was in, since that is
    the format isort will read it back in.

    Args:
        existing: The location of an existing config file
        output: The output location for the new config file.
        src_paths: A list of directories to consider source paths

    Raises:
        ValueError: If the config file is not one isort can read.
    """
    if existing.suffix == ".toml":
        _generate_toml_config(existing, output, src_paths)
        return

    if existing.suffix in _INI_SUFFIXES:
        _generate_ini_config(existing, output, src_paths)
        return

    raise ValueError(f"Unexpected isort config file '{existing}'.")


@contextlib.contextmanager
def determinism_patch() -> Generator[None, None, None]:
    """A context manager for applying deterministic behavior to the python stdlib."""

    def _no_realpath(path, **kwargs):  # type: ignore
        """Avoid resolving symlinks and instead, simply convert paths to absolute."""
        del kwargs
        return os.path.abspath(path)

    # Avoid sandbox escapes
    old_realpath = os.path.realpath
    os.path.realpath = cast(Any, _no_realpath)

    try:
        yield
    finally:
        os.path.realpath = old_realpath


def _load_args() -> Sequence[str]:
    """Load command line arguments from the environment."""
    if "BAZEL_TEST" in os.environ and "RULES_VENV_ISORT_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise OSError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["RULES_VENV_ISORT_RUNNER_ARGS_FILE"])
        return arg_file.read_text(encoding="utf-8").splitlines()

    return sys.argv[1:]


def _get_runfiles_dir() -> Path:
    """Locate the runfiles directory from the environment."""
    # Determined by rules_venv
    if "RULES_VENV_RUNFILES_DIR" in os.environ:
        return Path(os.environ["RULES_VENV_RUNFILES_DIR"])
    if "RUNFILES_DIR" in os.environ:
        return Path(os.environ["RUNFILES_DIR"])

    raise OSError("Unable to locate runfiles directory.")


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

        with determinism_patch():
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
