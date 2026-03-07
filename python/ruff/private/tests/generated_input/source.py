"""A module which consumes a Bazel generated soruce.

Used for tests against ruff rules.
"""

from python.ruff.private.tests.generated_input.generated import (
    greeting,
)


def say_greeting(name: str) -> None:
    """Print a greeting for the given name."""

    greeting(name)
