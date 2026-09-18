"""Read a namespace-packaged installed package through its stubs."""

from acme.gadgets.core import volume


def box(width: float, height: float, depth: float) -> float:
    """Measure a box through the stubbed namespace package.

    Args:
        width: The box's width.
        height: The box's height.
        depth: The box's depth.

    Returns:
        The box's volume.
    """
    return volume(width, height, depth)
