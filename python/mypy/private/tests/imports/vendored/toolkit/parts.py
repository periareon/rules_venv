"""The submodule the rest of the package reaches by absolute name."""

import dataclasses


@dataclasses.dataclass(frozen=True)
class Part:
    """Something a `Whole` is assembled from."""

    name: str
    count: int


def _normalize(name: str) -> str:
    """Put a name in the form a part is stored under.

    Private, and reached from outside all the same by the tests that
    cover this module -- the ordinary reason a name is spelled with an
    underscore and still imported. Nothing standing in for this module
    can forward it: a star import skips underscore names whatever the
    module says about them, so the only thing that carries it is the
    published cache entry itself, found under the name it was published
    as.
    """
    return name.strip().lower()
