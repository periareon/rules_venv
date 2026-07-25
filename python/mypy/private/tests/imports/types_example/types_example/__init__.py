"""Simple types for mypy."""

import enum


class ColorType(enum.IntEnum):
    """Color class"""

    RED = 1
    GREEN = 2
    BLUE = 3


MaybeIntsList = list[int | None]
