"""Represent interactions with generated."""

from python.mypy.private.tests.generated_input.generated import greeting


def say_hello(name: str) -> None:
    """Say hello to someone

    Args:
        name: The name of the person to greet.
    """

    greeting(name)
