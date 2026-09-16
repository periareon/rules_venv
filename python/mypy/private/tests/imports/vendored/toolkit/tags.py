"""A submodule nothing outside the package ever imports by name.

`whole` imports it, which is what makes it an attribute of the package,
and that is the only way a consumer gets at it. Reaching it that way is
worth a module of its own because it is the one case a star import
cannot answer: a package does not define its own submodules, so nothing
about `toolkit` says `tags` unless something says it outright.
"""

import dataclasses


@dataclasses.dataclass(frozen=True)
class Tag:
    """A label a part can be marked with."""

    text: str
