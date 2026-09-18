"""A package the module that types against it does not depend on.

A real one of these is the optional extra a library supports without
requiring: present in some builds, absent in others, and the library has
to say something about it either way. Here it exists only so that one
target can be built without it and another with it.
"""


# The class exists to be named from a module that cannot import it, so
# one attribute and a way to print it is the whole of what it needs.
# pylint: disable-next=too-few-public-methods
class Widget:
    """Something a renderer may be handed, where there is one to hand."""

    def __init__(self, label: str) -> None:
        """Record what the widget is called."""
        self.label = label

    def __repr__(self) -> str:
        """Describe the widget by its label."""
        return f"Widget({self.label!r})"
