"""Reach a sibling by the package's own short name, not by a relative one.

This is the spelling that puts both of the package's names in play at
once. The signatures below are written in terms of the short one, while
the cache this module is published to is keyed by the workspace-relative
one, so the two have to name the same `Part` and not merely two classes
that look alike. Relative imports would not ask that question; only
naming the package outright does.
"""

import toolkit.parts
import toolkit.tags
from toolkit.parts import Part


def assemble(names: list[str]) -> list[Part]:
    """One single-count part per name."""
    return [toolkit.parts.Part(name=name, count=1) for name in names]


def tag(part: Part) -> "toolkit.tags.Tag":
    """Label a part.

    Importing `toolkit.tags` here is the whole of what makes it an
    attribute of `toolkit`, for this module and for anyone reading the
    package out of the cache this action publishes.
    """
    return toolkit.tags.Tag(text=part.name)


def total(parts: list[Part]) -> int:
    """How many pieces the parts come to."""
    return sum(part.count for part in parts)
