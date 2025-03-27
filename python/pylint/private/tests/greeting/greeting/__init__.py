"""A module for generating greeting messages."""


def greeting(name: str) -> str:
    """Generate a greeting message.

    Args:
        name: The name of the entity to greet.

    Returns:
        The greeting.
    """
    return f"Hello, {name}"
