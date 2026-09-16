"""Read a type off a dependency that does not check clean.

The name below is defined perfectly well by `:faulty`, in a module that
happens to hold an unrelated error elsewhere. If the dependency's action
published no cache for that module, this import resolves against the
empty stand-in left in the source's place and `describe` is simply not
there -- an error here, several targets away from anything that looks
wrong, and about a file this target is not allowed to see.
"""

from python.mypy.private.tests.unchecked.faulty import describe


def label(name: str) -> str:
    """Label a name through the unchecked dependency.

    Args:
        name: The name to label.

    Returns:
        The labelled name.
    """
    return describe(name)
