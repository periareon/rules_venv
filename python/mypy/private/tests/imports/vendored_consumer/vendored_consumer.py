"""Consume a vendored package whose modules name each other absolutely.

`//python/mypy/private/tests/imports/vendored` is reached here by the
short name its `imports` root gives it, which is the only name any of it
can be spelled by: its own modules pin that spelling.

The dependency is analyzed by its own action and arrives here as a cache
rather than as sources, and that cache is keyed by the workspace-
relative name instead. So every name below is answered by a re-export
standing at the short name, and getting real types out of one -- rather
than the empty module a missing cache entry leaves behind -- is what
says the two names reached the same published types.
"""

import toolkit
from toolkit.parts import Part
from toolkit.whole import assemble, tag, total


def bill_of_materials(names: list[str]) -> tuple[list[Part], int]:
    """The parts a name list assembles into, and how many pieces that is."""
    parts = assemble(names)
    return parts, total(parts)


def first_name(names: list[str]) -> str:
    """The name of the first part, read off the dataclass field."""
    return assemble(names)[0].name


def normalized(name: str) -> str:
    """Reach a private name of the dependency, as its own tests do.

    `:vendored` declares the `imports` root that gives its modules their
    short names, so this is the name that package publishes under and
    the cache entry behind it holds everything the module defines,
    underscore names included. A stand-in that merely re-exported the
    module would carry the rest and drop this one.

    Args:
        name: The name to normalize.

    Returns:
        The normalized name.
    """
    # pylint: disable=protected-access
    return toolkit.parts._normalize(name)


def labelled(names: list[str]) -> list[toolkit.tags.Tag]:
    """Tag every part, naming a submodule this file never imported.

    `toolkit.tags` is an attribute of the package only because something
    inside the package imported it, and that happened in another action
    -- so a star import of the package carries no trace of it, and what
    stands at the short name has to say it again. Without that, this is
    the error a consumer actually sees: a module with no such attribute,
    reported several targets away from anything that looks wrong.
    """
    return [tag(part) for part in assemble(names)]
