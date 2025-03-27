"""A script for applying isort fixes to Bazel targets."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

from python.runfiles import Runfiles  # type: ignore

from python.isort.private.isort_runner import generate_config_with_projects

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


def query_targets(query_string: str, bazel: Path, workspace_dir: Path) -> List[str]:
    """Query python sources of bazel targets to run isort on

    Args:
        query_string: A query string to pass to `bazel query`.
        bazel: The path to a Bazel binary.
        workspace_dir: The location fo the Bazel workspace root.

    Returns:
        A list of targets provided by `bazel query`.
    """
    query_result = subprocess.run(
        [
            str(bazel),
            "query",
            query_string,
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


def query_imports(
    query_string: str, bazel: Path, workspace_dir: Path
) -> Dict[str, Dict[str, List[str]]]:
    """Query python sources of bazel targets to run isort on

    Args:
        query_string: A query string to pass to `bazel query`.
        bazel: The path to a Bazel binary.
        workspace_dir: The location fo the Bazel workspace root.

    Returns:
        A list of paths to included as isort src paths.
    """
    query_result = subprocess.run(
        [
            str(bazel),
            "query",
            query_string,
            "--noimplicit_deps",
            "--keep_going",
            "--output=streamed_jsonproto",
        ],
        cwd=str(workspace_dir),
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )

    imports = {}
    for stream in query_result.stdout.splitlines():
        result = json.loads(stream)
        rule = result["rule"]
        label = rule["name"]
        imports[label] = {"imports": [str(workspace_dir)]}
        package, _, _ = label.partition(":")
        for attr in rule["attribute"]:
            if attr["name"] != "imports":
                continue
            if "stringListValue" not in attr:
                continue
            for value in attr["stringListValue"]:
                import_path = workspace_dir / f"{package}/{value}".strip("/.")
                imports[label]["imports"].append(str(import_path))

        imports[label]["imports"] = sorted(imports[label]["imports"])

    return imports


def run_isort(
    targets: List[str],
    settings_path: Path,
    workspace_dir: Path,
) -> None:
    """Run isort in a subprocess

    Args:
        targets: A list of source targets to format
        settings_path: The path to the isort config file.
        workspace_dir: The Bazel workspace root.
        repo_imports: Python package ids which represent global packages to consider first party.
        target_imports: Optional paths to directories that contain first party packages.
    """
    if not targets:
        return

    # Convert the targets to source paths
    sources = [target.replace(":", "/").replace("//", "") for target in targets]

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


# pylint: disable=too-many-locals
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

    existing_settings = _rlocation(runfiles, os.environ["ISORT_SETTINGS_PATH"])

    # query all targets with no specified imports
    # Query explanation:
    # Filter all local targets ending in `*.py`.
    #     Get all source files.
    #         Get direct dependencies from targets matching the given scope.
    #         Except for targets tag to ignore formatting
    srcs_query_template = r"""let scope = {scope} in filter("^//.*\.py$", kind("source file", deps($scope except attr(tags, "(^\[|, )(noformat|no-format|no_format|no-isort-format|no_isort_format)(, |\]$)", $scope), 1)))"""  # pylint: disable=line-too-long

    # Query for targets which do not specify `imports = ["."]`
    srcs_scope = r"""kind(py_.*, set({scope}) except attr(imports, "[\.\w\d\-_]+", kind("py_*", set({scope}))))""".format(  # pylint: disable=line-too-long
        scope=" ".join(args.scope)
    )

    src_targets = query_targets(
        srcs_query_template.replace("{scope}", srcs_scope),
        args.bazel,
        workspace_dir,
    )

    # query all targets with any import paths provided
    imports_query_template = r"""attr(imports, "[\.\w\d\-_]+", kind("py_*", set({scope})) except attr(tags, "(^\[|, )(noformat|no-format|no_format|no-isort-format|no_isort_format)(, |\]$)", set({scope})) )"""  # pylint: disable=line-too-long
    imports_scope = imports_query_template.replace("{scope}", " ".join(args.scope))
    imports = query_imports(
        query_string=imports_scope, bazel=args.bazel, workspace_dir=workspace_dir
    )

    # pylint: disable-next=consider-using-dict-items
    for target in imports:
        imports[target]["src_targets"] = query_targets(
            srcs_query_template.replace("{scope}", target),
            args.bazel,
            workspace_dir,
        )

    with tempfile.TemporaryDirectory(prefix="isort-fixer-") as tmp_dir:
        settings_path = Path(tmp_dir) / existing_settings.name
        generate_config_with_projects(
            existing=existing_settings,
            output=settings_path,
            src_paths=[str(workspace_dir)],
        )

        # Run isort on all sources
        run_isort(
            targets=src_targets,
            settings_path=settings_path,
            workspace_dir=workspace_dir,
        )

        for target, data in imports.items():
            sanitized_target = (
                target.replace("@", "at").replace("/", "_").replace(":", "_")
            )
            settings_path = Path(tmp_dir) / sanitized_target / existing_settings.name
            settings_path.parent.mkdir(exist_ok=True, parents=True)

            generate_config_with_projects(
                existing=existing_settings,
                output=settings_path,
                src_paths=data["imports"],
            )

            run_isort(
                targets=data["src_targets"],
                settings_path=settings_path,
                workspace_dir=workspace_dir,
            )


if __name__ == "__main__":
    main()
