"""Example code for a py_wheel_library test."""

from python.wheel.private.tests.with_internal_deps.blue import blue
from python.wheel.private.tests.with_internal_deps.green import green
from python.wheel.private.tests.with_internal_deps.red import red


def rgb_colors() -> list[str]:
    """Return a list of red, green, and blue color codes

    Returns:
        RGB color codes
    """

    return [
        red.color(),
        green.color(),
        blue.color(),
    ]
