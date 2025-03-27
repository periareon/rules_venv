"""Show consumption of types from another package in the repo."""

from typing import List

from python.mypy.private.tests.repo_absolute_imports.types_example import (
    ColorType,
    MaybeIntsList,
)


def color_name(color: int) -> str:
    """Get the color name"""
    if color == ColorType.RED:
        return "red"

    if color == ColorType.BLUE:
        return "blue"

    if color == ColorType.GREEN:
        return "green"

    raise ValueError(f"Unexpected color code: {color}")


def stringify_numbers(maybe_numbers: MaybeIntsList) -> List[str]:
    """Get a list of color names."""
    return [str(i) for i in maybe_numbers]
