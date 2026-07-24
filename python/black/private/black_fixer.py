"""A script for applying black fixes to Bazel targets."""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Sequence

import black
from python.runfiles import Runfiles

from python.private import target_query

_IGNORE_TAGS: Sequence[str] = (
    "noformat",
    "no_format",
    "no_black_format",
    "no_black",
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--bazel",
        type=Path,
        help="The path to a `bazel` binary. The `BAZEL_REAL` environment variable can also be used to set this value.",
    )
    parser.add_argument(
        "scope",
        nargs="*",
        default=["//...:all"],
        help="Bazel package or target scoping for formatting. E.g. `//...`, `//some:target`.",
    )

    parsed_args = parser.parse_args()

    if not parsed_args.bazel:
        parsed_args.bazel = target_query.find_bazel()

    return parsed_args


def run_black(
    sources: List[str],
    settings_path: Path,
    workspace_dir: Path,
) -> None:
    """Run black on a given set of sources

    Args:
        sources: A list of source targets to format.
        settings_path: The path to the isort config file.
        workspace_dir: The Bazel workspace root.
    """
    if not sources:
        return

    black_args = ["--config", str(settings_path)]

    if "RULES_VENV_BLACK_DEBUG" in os.environ:
        black_args.append("--verbose")

    black_args.extend(sources)

    exit_code = 0
    old_argv = list(sys.argv)
    sys.argv = [sys.argv[0]] + black_args
    old_cwd = os.getcwd()
    os.chdir(workspace_dir)
    try:
        black.patched_main()

    except SystemExit as exc:
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, str):
            exit_code = int(exc.code)
        else:
            exit_code = exc.code
    finally:
        os.chdir(old_cwd)
        sys.argv = old_argv

    if exit_code != 0:
        sys.exit(exit_code)


def main() -> None:
    """The main entry point"""
    args = parse_args()

    if "BUILD_WORKSPACE_DIRECTORY" not in os.environ:
        raise EnvironmentError(
            "BUILD_WORKSPACE_DIRECTORY is not set. Is the process running under Bazel?"
        )

    workspace_dir = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError(
            "RUNFILES_MANIFEST_FILE and RUNFILES_DIR are not set. Is python running under Bazel?"
        )

    settings = target_query.rlocation(runfiles, os.environ["BLACK_SETTINGS_PATH"])

    sources = target_query.resolve_source_paths(
        scope=args.scope,
        bazel=args.bazel,
        workspace_dir=workspace_dir,
        ignore_tags=_IGNORE_TAGS,
    )

    run_black(
        sources=sources,
        settings_path=settings,
        workspace_dir=workspace_dir,
    )


if __name__ == "__main__":
    main()
