"""A module for calculating fibonacci sequences"""


def fibonacci(n: int) -> int:
    """Return the fibonacci sequence for a given number of steps in.

    Args:
        n: The steps of a fibonacci sequence.

    Returns:
        The fibonacci value `n` steps in.
    """

    if n < 2:
        return n

    n1 = 0
    n2 = 1
    for _ in range(0, n):
        result = n1 + n2
        n1 = n2
        n2 = result

    return n2
