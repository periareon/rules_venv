"""Fixture exercising ruff isort first-party classification.

The three import groups (stdlib, third-party, first-party) are separated
by blank lines. The first-party group mixes:

  * an import from a real source module (`fibonacci_of`),
  * an import from a `write_file`-generated module (`greet`), and
  * an import from a `py_cc_extension`-produced compiled module
    (`native_module`).

Together these cover source, generated, and compiled contributions to
the aspect's first-party enumeration. Ruff's `I001` rule fails if any of
these belongs in a different group; if `python` is misclassified as
third-party, or if any of the three module kinds is dropped from the
first-party set, ruff will want the groups merged.
"""

import argparse

import tomlkit

from python.ruff.private.tests.imports.fibonacci import fibonacci_of
from python.ruff.private.tests.isort import native_module  # type: ignore[attr-defined]
from python.ruff.private.tests.isort.generated.greeter import greet


def build() -> tuple[argparse.ArgumentParser, str, int, str, object]:
    """Reference every import so `F401`-style rules never mask `I001`."""
    return (
        argparse.ArgumentParser(),
        tomlkit.__name__,
        fibonacci_of(5),
        greet("world"),
        native_module,
    )
