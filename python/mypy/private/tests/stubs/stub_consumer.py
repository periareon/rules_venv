"""Read an installed package whose types live in a stub distribution."""

from shapes.core import area


def rectangle(width: float, height: float) -> float:
    """Measure a rectangle through the stubbed package.

    Args:
        width: The rectangle's width.
        height: The rectangle's height.

    Returns:
        The rectangle's area.
    """
    return area(width, height)
