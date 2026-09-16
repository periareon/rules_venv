"""A consumer that lists a dependency's source among its own."""

from python.mypy.private.tests.pruning.pruned_shared import shared


def consume(value: int) -> str:
    """Render a value through the shared module."""
    return shared(value)
