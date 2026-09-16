"""Reach a dependency that `imports` has given a shorter name.

`//python/mypy/private/tests/imports/types_example` puts its sources
under a nested import root, so mypy names the module `types_example` and
that is the only name a single pass over its sources can cache it under.
Spelling the workspace-relative name instead is still legal -- the
workspace root is on the path too -- so this target stands for the case
the dependency's own action has to anticipate: a consumer resolving a
name the dependency was never asked about. Getting `ColorType` here
means the dependency published both.
"""

from python.mypy.private.tests.imports.types_example.types_example import ColorType


def brightest() -> int:
    """The largest value the shadowed module defines."""
    return max(color.value for color in ColorType)
