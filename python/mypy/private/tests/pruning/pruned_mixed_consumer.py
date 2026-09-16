"""Consumer of a library that mixes checked and generated sources."""

from python.mypy.private.tests.pruning.pruned_mixed import mixed


def mixed_consumer(name: str) -> str:
    """Greet by way of the mixed library.

    Args:
        name: The name to greet.

    Returns:
        The greeting.
    """
    return mixed(name)
