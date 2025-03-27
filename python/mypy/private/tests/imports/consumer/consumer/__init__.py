"""Show consumption of types from another package in the repo."""

from typing import List, Union

from types_example import (
    ColorType,
    MaybeIntsList,
)


def color_name(color: Union[int, ColorType]) -> str:
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
