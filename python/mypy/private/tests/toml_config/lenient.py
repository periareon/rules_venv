"""A module the workspace's own (strict) mypy config would reject."""


def untyped():
    """Return a number, without saying so.

    Returns:
        The number.
    """
    return 42
