"""A python module designed to test coverage"""

from . import submod  # noqa: F401


def divide(num1: int, num2: int) -> float:
    """Divide two numbers

    Args:
        num1: The first number
        num2: The second number

    Returns:
        The result of dividing num1 into num2.
    """
    if num2 == 0:
        raise ValueError("Cannot divide by 0")

    return num1 / num2


def say_greeting(name: str) -> None:  # pragma: no cover
    """Print a greeting

    Args:
        name: The name of the character to greet.
    """
    print(submod.greeting(name))
