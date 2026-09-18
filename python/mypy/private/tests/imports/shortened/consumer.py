"""Reach a dependency by a shorter name than the dependency itself used.

`:helpers` declares no `imports` root of its own, so its action names its
modules for the workspace root: `python.mypy...shortened.helpers.support`
and nothing else. This target adds its own directory as a root, which
puts the very same file on the search path a second time, under
`helpers.support`.

That is the name looked up below, and it is not the name the dependency
published. Only a re-export standing at it reaches what the dependency
did publish; without one, the sources are already out of the venv and
what is left to resolve against is the empty stand-in -- `describe`
goes missing from a module that plainly defines it.
"""

from helpers.support import describe


def label(name: str) -> str:
    """Label a name through the dependency.

    Args:
        name: The name to label.

    Returns:
        The labelled name.
    """
    return describe(name)
