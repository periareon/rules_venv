"""A script which consumes imports through import paths shared by multiple imports.

All tests in `rules_venv` live under `python.venv.private.tests` and the
`python.within_second_python.py_dep` packages uses the `imports` attribute to
expose this module at that location.
"""

from pathlib import Path

# pylint: disable-next=no-name-in-module
from python.within_second_python.py_dep import generate_greeting  # type: ignore

from python.runfiles import Runfiles  # type: ignore


def generate_greeting_followup(name: str) -> str:
    """Generate a greeting"""
    return f"{generate_greeting(name)}! How are you?"


def load_data() -> str:
    """Load data from a runfile."""
    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles.")

    rlocationpath = (
        "rules_venv/python/venv/private/tests/import_duplicates/consumer/data.txt"
    )
    runfile = runfiles.Rlocation(rlocationpath)
    if not runfiles:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")

    return Path(runfile).read_text(encoding="utf-8")
