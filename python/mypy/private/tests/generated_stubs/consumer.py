"""Consumer of an untyped module with generated stubs."""

from python.mypy.private.tests.generated_stubs.untyped import greeting


def say_hello(name: str) -> str:
    """Say hello to someone using the untyped module.

    Args:
        name: The name to greet.

    Returns:
        The greeting string.
    """
    return greeting(name)
