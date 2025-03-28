"""A script for checking that coverage data has been reported."""

import os
import re
from pathlib import Path

REQUIRED_PATHS = [
    "python/pytest/private/tests/coverage/empty_config/lib/__init__.py",
    "python/pytest/private/tests/coverage/empty_config/lib/submod/__init__.py",
    "python/pytest/private/tests/coverage/multi_file/lib/__init__.py",
    "python/pytest/private/tests/coverage/multi_file/lib/submod/__init__.py",
    "python/pytest/private/tests/coverage/simple/lib/__init__.py",
    "python/pytest/private/tests/coverage/simple/lib/submod/__init__.py",
    "python/pytest/private/tests/coverage/split_collection/lib/__init__.py",
    "python/pytest/private/tests/coverage/split_collection/lib/submod/__init__.py",
]


def find_workspace_root() -> Path:
    """Locate the `rules_venv` workspace root."""
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        return Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])

    this_file = Path(__file__)
    return this_file.parent.parent.parent


def main() -> None:
    """The main entrypoint."""
    workspace_root = find_workspace_root()

    report_path = workspace_root / "bazel-out/_coverage/_coverage_report.dat"

    text = report_path.read_text(encoding="utf-8")

    # Ensure any coverage was collected at all.
    assert re.search(
        r"^SF:.*\.py$", text, re.MULTILINE
    ), "Failed to find any Python coverage"

    # Check that specific files have coverage.
    for required in REQUIRED_PATHS:
        regex_required = required.replace(".", "\\.")
        assert re.search(
            rf"^SF:{regex_required}$", text, re.MULTILINE
        ), f"Failed to find python coverage for {required}"

    print("Coverage was found!")


if __name__ == "__main__":
    main()
