"""Fixture exercising ruff isort first-party classification.

The three import groups (stdlib, third-party, first-party) are separated
by blank lines. The first-party group mixes an import from a real source
module (`fibonacci_of`) with one from a `write_file`-generated module
(`greet`) so this test also covers generated-source contributions to the
aspect's first-party enumeration. Ruff's `I001` rule fails if any of
these belongs in a different group; if `python` is misclassified as
third-party, or if the generated module is dropped from the first-party
set, ruff will want the groups merged.
"""

import argparse

import tomlkit

from python.ruff.private.tests.imports.fibonacci import fibonacci_of
from python.ruff.private.tests.isort.generated.greeter import greet


def build() -> tuple[argparse.ArgumentParser, str, int, str]:
    """Reference every import so `F401`-style rules never mask `I001`."""
    return (
        argparse.ArgumentParser(),
        tomlkit.__name__,
        fibonacci_of(5),
        greet("world"),
    )
