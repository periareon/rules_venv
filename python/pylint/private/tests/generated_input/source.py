"""A module which consumes a Bazel generated soruce.

Used for tests against pylint rules.
"""

from python.pylint.private.tests.generated_input.generated import (  # type: ignore
    greeting,
)


def say_greeting(name: str) -> None:
    """Print a greeting for the given name."""

    greeting(name)
