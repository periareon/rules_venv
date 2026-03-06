"""The fibonacci module."""


def fibonacci_of(step: int) -> int:
    """Compute the fibonacci value for a requested sequence number.

    Args:
        step: The steps of a fibonacci sequence.

    Returns:
        The fibonacci step based on `step`.
    """

    if step in {0, 1}:
        return step
    return fibonacci_of(step - 1) + fibonacci_of(step - 2)
