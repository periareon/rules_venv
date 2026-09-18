"""Depend on both halves, which is what makes the two disagree.

The renderer was analyzed without the package it names and this target
has both, so mypy here can resolve a name the renderer's own action
could not. Taking the renderer's cached answer as final is what keeps
its source out of this action; going back to the source would find the
stand-in left in its place and lose `render` altogether.
"""

from sidecar import Widget

from python.mypy.private.tests.optional_import.renderer import render


def describe(label: str) -> str:
    """Describe a widget by handing it to the renderer.

    Args:
        label: What to call the widget.

    Returns:
        The renderer's description of it.
    """
    return render(Widget(label))
