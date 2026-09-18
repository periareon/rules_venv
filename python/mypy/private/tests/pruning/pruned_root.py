"""The top of the dependency tree, two edges away from the leaf."""

from python.mypy.private.tests.pruning.pruned_middle import middle


def root(value: int) -> str:
    """Render a value, by way of the middle."""
    return middle(value)
