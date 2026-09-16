"""Name a package this target does not depend on.

An optional extra is the ordinary reason to do this: the module has
something to say about a type it only sometimes has, so it names the
package and tells mypy not to mind when the name goes nowhere.

mypy records that the name went nowhere, and rechecks the module the
moment it goes somewhere -- which is exactly what happens in a consumer
that depends on the package as well as on this. The recheck needs this
file, and a consumer holding this target's cache is not given it, so
everything the consumer wanted from this module would come back empty.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sidecar import Widget  # type: ignore[import-not-found]


def render(widget: "Widget | None" = None) -> str:
    """Describe what there is to render.

    Args:
        widget: The widget to describe, if there is one.

    Returns:
        A description of the widget, or of its absence.
    """
    return "nothing" if widget is None else repr(widget)
