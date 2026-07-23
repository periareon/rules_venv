"""A script for applying ruff format fixes to Bazel targets."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from python.runfiles import Runfiles

from python.ruff.private.ruff_runner import (
    Modes,
    collect_first_party_names_from_dir,
    find_ruff,
    user_known_first_party,
)


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
    """Parse command line arguments.

    Any arguments after a `--` delimiter are captured on the returned namespace
    as `ruff_args` and forwarded verbatim to the underlying `ruff` invocation.
    """
    argv = sys.argv[1:]
    if "--" in argv:
        split = argv.index("--")
        pre_args = argv[:split]
        ruff_args = argv[split + 1 :]
    else:
        pre_args = argv
        ruff_args = []

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
        help="Bazel package or target scoping for formatting. E.g. `//...`, `//some:target`. "
        "Arguments after a `--` delimiter are forwarded to `ruff` (e.g. `-- --unsafe-fixes`).",
    )

    parsed_args = parser.parse_args(pre_args)
    parsed_args.ruff_args = ruff_args

    if not parsed_args.bazel:
        parsed_args.bazel = find_bazel()

    return parsed_args


def query_targets(
    scope: Sequence[str], bazel: Path, workspace_dir: Path, mode: Modes
) -> List[str]:
    """Query for all source targets of all python targets within a given workspace.

    Args:
        scope: The scope of the Bazel query (e.g. `//...`)
        bazel: The path to a Bazel binary.
        workspace_dir: The workspace root in which to query.
        mode: The current operating ruff mode.

    Returns:
        A list of all discovered targets.
    """
    # Query explanation:
    # Filter targets down to anything beginning with `//` and ends with `.py`.
    #       Collect source files.
    #           Collect dependencies of targets for a given scope.
    #           Except for targets tagged to ignore formatting
    #
    query_template = r"""filter("^//.*\.py$", kind("source file", deps(set({scope}) except attr(tags, "(^\[|, )({ignore_tags})(, |\]$)", set({scope})), 1)))"""

    common_tags = [
        "no-ruff",
        "noruff",
        "no_ruff",
    ]

    ignore_tags = {
        Modes.FORMAT: common_tags
        + [
            "nofmt",
            "noformat",
            "no-format",
            "no_format",
            "no-fmt",
            "no_fmt",
            "no-ruff-format",
            "no_ruff_format",
            "no_ruff_fmt",
        ],
        Modes.CHECK: common_tags
        + [
            "nolint",
            "no-lint",
            "no_lint",
            "no-ruff-lint",
            "no_ruff_lint",
        ],
    }

    query_result = subprocess.run(
        [
            str(bazel),
            "query",
            query_template.replace("{scope}", " ".join(scope)).replace(
                "{ignore_tags}", "|".join(ignore_tags[mode])
            ),
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


def workspace_first_party_override(
    workspace_dir: Path, settings_path: Path
) -> Optional[str]:
    """Build a ``lint.isort.known-first-party`` override for the fixer.

    Mirrors the runner's runfiles-based override but sources names from the
    workspace on disk (which the fixer runs against). Keeping these two paths
    aligned prevents fix/check disagreement over what counts as first-party.
    """
    discovered = collect_first_party_names_from_dir(workspace_dir)
    combined = set(discovered) | set(user_known_first_party(settings_path))
    if not combined:
        return None
    quoted = ", ".join(json.dumps(name) for name in sorted(combined))
    return f"lint.isort.known-first-party = [{quoted}]"


# pylint: disable-next=too-many-arguments
def run_ruff_fix(
    ruff: Path,
    sources: List[str],
    settings_path: Path,
    workspace_dir: Path,
    mode: Modes,
    *,
    extra_args: Sequence[str] = (),
) -> None:
    """Run ruff format on a given set of sources

    Args:
        ruff: The path to the ruff binary.
        sources: A list of source targets to format.
        settings_path: The path to the ruff config file.
        workspace_dir: The Bazel workspace root.
        mode: The current fix mode.
        extra_args: Additional arguments forwarded verbatim to `ruff`.

    """
    if not sources:
        return

    ruff_args = [
        str(ruff),
        "--config",
        str(settings_path),
    ]

    first_party_override = workspace_first_party_override(workspace_dir, settings_path)
    if first_party_override is not None:
        ruff_args.extend(["--config", first_party_override])
        if "RULES_VENV_RUFF_DEBUG" in os.environ:
            print(
                f"ruff-fixer: first-party override: {first_party_override}",
                file=sys.stderr,
            )

    if mode == Modes.CHECK:
        ruff_args.extend(
            [
                "check",
                "--fix",
            ]
        )
    elif mode == Modes.FORMAT:
        ruff_args.extend(
            [
                "format",
            ]
        )
    else:
        raise ValueError(f"Unexpected mode: {mode}")

    if "RULES_VENV_RUFF_DEBUG" in os.environ:
        ruff_args.append("--verbose")

    ruff_args.extend(extra_args)

    ruff_args.extend(sources)

    result = subprocess.run(
        ruff_args,
        cwd=str(workspace_dir),
        check=False,
    )

    if result.returncode != 0:
        sys.exit(result.returncode)


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

    settings = _rlocation(runfiles, os.environ["RUFF_SETTINGS_PATH"])
    mode = Modes(os.environ["RUFF_MODE"])

    # Query for all sources
    targets = query_targets(
        scope=args.scope, bazel=args.bazel, workspace_dir=workspace_dir, mode=mode
    )

    sources = [pathify(t) for t in targets]

    ruff_bin = None
    rlocationpath = os.getenv("RUFF_RLOCATIONPATH")
    if rlocationpath:
        ruff_bin = _rlocation(runfiles, rlocationpath)

    ruff_bin = find_ruff(ruff_bin)

    run_ruff_fix(
        ruff=ruff_bin,
        sources=sources,
        settings_path=settings,
        workspace_dir=workspace_dir,
        mode=mode,
        extra_args=args.ruff_args,
    )


if __name__ == "__main__":
    main()
