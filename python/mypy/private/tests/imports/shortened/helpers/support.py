"""Types published under the name this target's own action gives them.

The target declares no `imports` root, so its action names this module
for the workspace root it sits under. The consumer names it something
shorter. Both names are of the same file, and the cache is keyed by
whichever one its producer used.
"""


def describe(name: str) -> str:
    """Render a name.

    Args:
        name: The name to render.

    Returns:
        The rendered name.
    """
    return f"<{name}>"
