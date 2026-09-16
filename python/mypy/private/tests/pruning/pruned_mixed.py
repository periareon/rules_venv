"""A checked source sharing a target with a generated module."""

from python.mypy.private.tests.pruning.pruned_mixed_generated import generated


def mixed(name: str) -> str:
    """Greet by way of the generated module beside this one.

    Args:
        name: The name to greet.

    Returns:
        The greeting.
    """
    return generated(name)
