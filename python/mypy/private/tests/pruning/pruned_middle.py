"""A library between the leaf and the root."""

from python.mypy.private.tests.pruning.pruned_leaf import leaf


def middle(value: int) -> str:
    """Render a value, by way of the leaf."""
    return leaf(value)
