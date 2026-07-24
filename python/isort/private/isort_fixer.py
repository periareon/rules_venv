"""A script for applying isort fixes to Bazel targets."""

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Sequence

from isort.main import main as isort_main
from python.runfiles import Runfiles

from python.isort.private.isort_runner import generate_config_with_projects
from python.private import target_query

_IGNORE_TAGS: Sequence[str] = (
    "noformat",
    "no_format",
    "no_isort_format",
    "no_isort",
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


def _expand_imports(target: target_query.TargetInfo, workspace_dir: Path) -> List[str]:
    """Expand a target's raw `imports` values to isort `src_paths`.

    Matches the runner's `//package/<imports_value>` construction and
    always includes the workspace root so intra-repo imports resolve.
    """
    paths = {str(workspace_dir)}
    for value in target.imports:
        joined = f"{target.package}/{value}".strip("/.")
        if joined:
            paths.add(str(workspace_dir / joined))
    return sorted(paths)


def run_isort(
    sources: Sequence[str],
    settings_path: Path,
    workspace_dir: Path,
) -> None:
    """Run isort in a subprocess

    Args:
        sources: Workspace-relative paths to `.py` files to format.
        settings_path: The path to the isort config file.
        workspace_dir: The Bazel workspace root.
    """
    if not sources:
        return

    isort_args = ["--settings-path", str(settings_path)]

    if "RULES_VENV_ISORT_DEBUG" in os.environ:
        isort_args.append("--verbose")
        settings_content = settings_path.read_text(encoding="utf-8")
        print(
            f"isort config:\n```\n{settings_content}\n```",
            file=sys.stderr,
        )

    isort_args.extend(sources)

    exit_code = 0
    old_cwd = os.getcwd()
    os.chdir(workspace_dir)
    try:
        isort_main(isort_args)

    except SystemExit as exc:
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, str):
            exit_code = int(exc.code)
        else:
            exit_code = exc.code
    os.chdir(old_cwd)

    if exit_code != 0:
        sys.exit(exit_code)


def _sanitize_label(label: str) -> str:
    return label.replace("@", "at").replace("/", "_").replace(":", "_")


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

    existing_settings = target_query.rlocation(
        runfiles, os.environ["ISORT_SETTINGS_PATH"]
    )

    # Single query for the entire scope. `imports`-carrying targets are
    # picked out below in Python — the old code ran one extra query per
    # such target, which dominated wall time on repos with many
    # `imports = ["."]` libraries.
    targets = target_query.query_python_targets(
        scope=args.scope,
        bazel=args.bazel,
        workspace_dir=workspace_dir,
        ignore_tags=_IGNORE_TAGS,
    )

    # Bucket 1: targets without an `imports` attribute — one isort run,
    # workspace-only `src_paths`, files from every such target unioned.
    default_sources = sorted(
        {file for target in targets if not target.imports for file in target.files}
    )
    # Bucket 2: one isort run per `imports`-carrying target so its
    # package-relative import paths land in that run's `src_paths`.
    imports_targets = [target for target in targets if target.imports]

    with tempfile.TemporaryDirectory(prefix="isort-fixer-") as tmp_dir:
        default_settings = Path(tmp_dir) / existing_settings.name
        generate_config_with_projects(
            existing=existing_settings,
            output=default_settings,
            src_paths=[str(workspace_dir)],
        )
        run_isort(
            sources=default_sources,
            settings_path=default_settings,
            workspace_dir=workspace_dir,
        )

        for target in imports_targets:
            per_target_settings = (
                Path(tmp_dir) / _sanitize_label(target.label) / existing_settings.name
            )
            per_target_settings.parent.mkdir(exist_ok=True, parents=True)
            generate_config_with_projects(
                existing=existing_settings,
                output=per_target_settings,
                src_paths=_expand_imports(target, workspace_dir),
            )
            run_isort(
                sources=target.files,
                settings_path=per_target_settings,
                workspace_dir=workspace_dir,
            )


if __name__ == "__main__":
    main()
