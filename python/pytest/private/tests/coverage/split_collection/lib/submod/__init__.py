"""A submodule designed to test coverage"""


# pylint: disable=redefined-builtin
def sum(num1: int, num2: int) -> int:
    """Add two numbers together.

    Args:
        num1: The first number
        num2: The second number

    Returns:
        The result of combining num1 and num2.
    """
    return num1 + num2


def greeting(name: str) -> str:
    """Generate a greeting message.

    Args:
        name: The name of the character to greet.

    Returns:
        The greeting message
    """
    if not name:
        raise ValueError("The name cannot be empty")

    return f"Hello, {name}!"
