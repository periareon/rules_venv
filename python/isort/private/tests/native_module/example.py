"""Fixture asserting standalone isort classifies compiled extensions as first-party.

The three import groups (stdlib, third-party, first-party) are separated by
blank lines. The first-party group mixes a `py_cc_extension`-produced
compiled module (`native_module`) with a plain source module (`HELPER_VALUE`)
so this test covers both kinds of first-party contributions. Standalone
isort staging the target's transitive closure into a venv should find both
and keep them grouped together; misclassification would surface as an
import-ordering diff.
"""

import argparse

import tomlkit

from python.isort.private.tests.native_module import native_module  # type: ignore
from python.isort.private.tests.native_module.helper import HELPER_VALUE


def build() -> tuple[argparse.ArgumentParser, str, object, int]:
    """Reference every import so downstream unused-import rules stay silent."""
    return (
        argparse.ArgumentParser(),
        tomlkit.__name__,
        native_module,
        HELPER_VALUE,
    )
