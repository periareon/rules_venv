"""A script for applying black fixes to Bazel targets."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence

import black
from python.runfiles import Runfiles  # type: ignore


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


def find_bazel() -> Path:
    """Locate a Bazel executable."""
    if "BAZEL_REAL" in os.environ:
        return Path(os.environ["BAZEL_REAL"])

    for filename in ["bazel", "bazel.exe", "bazelisk", "bazelisk.exe"]:
        path = shutil.which(filename)
        if path:
            return Path(path)

    raise FileNotFoundError("Could not locate a Bazel binary")


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
        parsed_args.bazel = find_bazel()

    return parsed_args


def query_targets(scope: Sequence[str], bazel: Path, workspace_dir: Path) -> List[str]:
    """Query for all source targets of all python targets within a given workspace.

    Args:
        scope: The scope of the Bazel query (e.g. `//...`)
        bazel: The path to a Bazel binary.
        workspace_dir: The workspace root in which to query.

    Returns:
        A list of all discovered targets.
    """
    # Query explanation:
    # Filter targets down to anything beginning with `//` and ends with `.py`.
    #       Collect source files.
    #           Collect dependencies of targets for a given scope.
    #           Except for targets tag to ignore formatting
    #
    # pylint: disable-next=line-too-long
    query_template = r"""filter("^//.*\.py$", kind("source file", deps(set({scope}) except attr(tags, "(^\[|, )(noformat|no-format|no-black-format)(, |\]$)", set({scope})), 1)))"""

    query_result = subprocess.run(
        [
            str(bazel),
            "query",
            query_template.replace("{scope}", " ".join(scope)),
            "--noimplicit_deps",
            "--keep_going",
        ],
        cwd=str(workspace_dir),
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )

    targets = query_result.stdout.splitlines()
    return targets


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

    if "RULES_BLACK_DEBUG" in os.environ:
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


def pathify(label: str) -> str:
    """Converts `//foo:bar` into `foo/bar`."""
    if label.startswith("@"):
        raise ValueError("External labels are unsupported", label)
    if label.startswith("//:"):
        return label[3:]
    return label.replace(":", "/").replace("//", "")


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

    settings = _rlocation(runfiles, os.environ["BLACK_SETTINGS_PATH"])

    # Query for all sources
    targets = query_targets(
        scope=args.scope,
        bazel=args.bazel,
        workspace_dir=workspace_dir,
    )

    sources = [pathify(t) for t in targets]

    run_black(
        sources=sources,
        settings_path=settings,
        workspace_dir=workspace_dir,
    )


if __name__ == "__main__":
    main()
