"""Consumer of a library whose only source is generated."""

from python.mypy.private.tests.pruning.pruned_generated import generated


def generated_consumer(name: str) -> str:
    """Greet by way of a library that has no source files at all.

    Args:
        name: The name to greet.

    Returns:
        The greeting.
    """
    return generated(name)
