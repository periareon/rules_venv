"""Entry point for running Mypy from Bazel."""

import argparse
import configparser
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence, TextIO, Union

from mypy.main import main as mypy_main
from python.runfiles import Runfiles


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
    """
    runfile = runfiles.Rlocation(rlocationpath, source_repo=os.getenv("TEST_WORKSPACE"))
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
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config-file",
        required=True,
        type=_maybe_runfile,
        help="The configuration file (mypy.ini).",
    )
    parser.add_argument(
        "--file",
        dest="sources",
        action="append",
        type=_maybe_runfile,
        required=True,
        help="The source file to run mypy on.",
    )
    parser.add_argument(
        "--workspace_name",
        type=str,
        required=True,
        help="The name of current workspace.",
    )
    parser.add_argument(
        "--marker",
        type=Path,
        help="The file to create as an indication that the action succeeded.",
    )

    parsed_args = parser.parse_args(args)

    if not parsed_args.sources:
        parser.error("No source files were provided.")

    return parsed_args


def _mypy_paths_from_sys_path(workspace_name: str) -> list[str]:
    """Extract workspace-local entries from ``sys.path`` for use as ``mypy_path``.

    The venv's site-init has already populated ``sys.path`` with resolved
    absolute paths derived from ``PyInfo.imports``.  We filter to entries
    that live under ``<runfiles_dir>/<workspace_name>`` so that mypy only
    sees the current workspace (not pip deps, external repos, or the
    stdlib).

    Subdirectory entries that contain an ``__init__.py`` are skipped.
    When ``explicit_package_bases = True``, mypy treats every
    ``mypy_path`` entry as a package root and scans directories with
    ``__init__.py`` for sibling modules.  If such a directory is ALSO
    reachable from the workspace root, mypy discovers the same files
    under two module names and raises a hard error.  Directories without
    ``__init__.py`` (e.g. generated stubs from pyo3) are only
    discoverable through the explicit ``imports`` path, so they are safe
    to include.
    """
    runfiles_dir = os.environ.get(
        "RULES_VENV_RUNFILES_DIR", os.environ.get("RUNFILES_DIR", "")
    )
    if not runfiles_dir:
        return []

    workspace_root = os.path.join(runfiles_dir, workspace_name)

    seen: set[str] = set()
    paths: list[str] = []
    for entry in sys.path:
        if entry != workspace_root and not entry.startswith(workspace_root + os.sep):
            continue
        if entry != workspace_root and os.path.isfile(
            os.path.join(entry, "__init__.py")
        ):
            continue
        if entry not in seen:
            seen.add(entry)
            paths.append(entry)
    return paths


def _generate_config(
    original_config: Path,
    mypy_paths: Sequence[str],
    tmp_dir: Path,
) -> Path:
    """Generate a copy of the mypy config with ``mypy_path`` populated.

    Most mypy path options (``mypy_path``, ``plugins``, etc.) resolve
    relative to the **working directory**, not the config file, so moving
    the config to a temp directory is safe for those.  The one exception
    is the ``MYPY_CONFIG_FILE_DIR`` variable that mypy auto-sets to the
    config file's parent directory; we preserve it by setting the env var
    explicitly before calling mypy (see ``main``).

    Args:
        original_config: Path to the user's mypy config file.
        mypy_paths: Absolute search paths to set as ``mypy_path``.
        tmp_dir: Temporary directory for the generated config.

    Returns:
        Path to the generated config file.
    """
    config = configparser.ConfigParser()
    config.read(str(original_config), encoding="utf-8")

    if not config.has_section("mypy"):
        config.add_section("mypy")

    seen = set(mypy_paths)
    all_paths = list(mypy_paths)

    existing = config.get("mypy", "mypy_path", fallback="")
    for entry in existing.replace(",", ":").replace("\n", ":").split(":"):
        entry = entry.strip()
        if entry and entry not in seen:
            seen.add(entry)
            all_paths.append(entry)

    config.set("mypy", "mypy_path", ":".join(all_paths))

    merged = tmp_dir / "mypy.ini"
    with open(merged, "w", encoding="utf-8") as f:
        config.write(f)
    return merged


def main() -> None:  # pylint: disable=too-many-branches
    """Mypy test runner main entry point."""
    if "BAZEL_TEST" in os.environ and "RULES_VENV_MYPY_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["RULES_VENV_MYPY_RUNNER_ARGS_FILE"])
        args = parse_args(arg_file.read_text(encoding="utf-8").splitlines())
    else:
        args = parse_args()

    stream = io.StringIO()
    stderr: Union[TextIO, io.StringIO]
    stdout: Union[TextIO, io.StringIO]
    if args.marker:
        stderr = stream
        stdout = stream
    else:
        stderr = sys.stderr
        stdout = sys.stdout

    tmp_dir = Path(tempfile.mkdtemp(prefix="bazel-mypy-", dir=os.getenv("TEST_TMPDIR")))
    exit_code = 0
    try:
        os.environ["HOME"] = str(tmp_dir)
        os.environ["USERPROFILE"] = str(tmp_dir)

        config_file = _generate_config(
            original_config=args.config_file,
            mypy_paths=_mypy_paths_from_sys_path(args.workspace_name),
            tmp_dir=tmp_dir,
        )

        # Mypy auto-sets MYPY_CONFIG_FILE_DIR to the config's parent dir
        # and users can reference it in paths (e.g. mypy_path =
        # $MYPY_CONFIG_FILE_DIR/stubs).  Since our copy lives in a temp
        # dir, point this back at the original location.
        os.environ["MYPY_CONFIG_FILE_DIR"] = str(args.config_file.parent)

        mypy_args = [
            "--config-file",
            str(config_file),
            "--cache-dir",
            str(tmp_dir / "mypy_cache"),
            "--no-incremental",
        ] + [str(src) for src in args.sources]

        mypy_main(args=mypy_args, stdout=stdout, stderr=stderr, clean_exit=True)

    except SystemExit as exc:
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, str):
            exit_code = int(exc.code)
        else:
            exit_code = exc.code

    finally:
        if "TEST_TMPDIR" not in os.environ:
            shutil.rmtree(tmp_dir)

    if args.marker:
        if exit_code == 0:
            args.marker.write_bytes(b"")
        else:
            print(stream.getvalue(), file=sys.stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
