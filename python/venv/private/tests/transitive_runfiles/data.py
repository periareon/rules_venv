"""Make data files available to external consumers"""

import os
from pathlib import Path

from python.runfiles import Runfiles  # type: ignore


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
    """
    runfile = runfiles.Rlocation(
        rlocationpath, source_repo=os.getenv("REPOSITORY_NAME")
    )
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def create_runfiles() -> Runfiles:
    """Construct a runfiles object."""
    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles.")
    return runfiles


def get_data(runfiles: Runfiles) -> str:
    """Access data from runfiles."""
    return (
        _rlocation(
            runfiles,
            "rules_venv/python/venv/private/tests/transitive_runfiles/data.txt",
        )
        .read_text(encoding="utf-8")
        .strip()
    )


def get_generated_data(runfiles: Runfiles) -> str:
    """Access generated data from runfiles."""
    return (
        _rlocation(
            runfiles,
            "rules_venv/python/venv/private/tests/transitive_runfiles/generated_data.txt",
        )
        .read_text(encoding="utf-8")
        .strip()
    )
