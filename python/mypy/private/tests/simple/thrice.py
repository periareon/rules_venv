"""Test module."""

from typing import Callable


def thrice(i: int, callback: Callable[[int], int]) -> int:
    """Invoke the callback 3 times."""
    return callback(callback(callback(i)))
