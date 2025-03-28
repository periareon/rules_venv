"""A test library for verifying the behavior of isort"""

from typing import Any


def assert_equal(left: Any, right: Any) -> None:
    """Assert that two things are equal

    Args:
        left: Thing one
        right: Thing two
    """
    assert left == right
