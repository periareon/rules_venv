"""Represent interactions with generated."""

from python.venv.private.tests.generated_srcs.generated import greeting


def say_hello(name: str) -> None:
    """Say hello to someone

    Args:
        name: The name of the person to greet.
    """

    print(greeting(name))
