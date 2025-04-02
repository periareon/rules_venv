"""Simple types for mypy."""

import enum
from typing import List, Optional


class ColorType(enum.IntEnum):
    """Color class"""

    RED = 1
    GREEN = 2
    BLUE = 3


MaybeIntsList = List[Optional[int]]
