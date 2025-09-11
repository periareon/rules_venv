"""Tests regression testing `pytest-xdist` args with `py_pytest_test`"""

import pytest


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


@pytest.mark.xdist_group("group_1")
def test_divide_by_zero() -> None:
    """Test attempting to divide by 0"""
    with pytest.raises(ValueError) as e_info:
        divide(3, 0)
        assert str(e_info) == "Cannot divide by 0"


@pytest.mark.xdist_group("group_1")
def test_sum() -> None:
    """Test addition"""
    assert 128 + 128 == 256


@pytest.mark.xdist_group("group_2")
def test_greeting() -> None:
    """Test greeting"""
    assert greeting("Mars") == "Hello, Mars!"


@pytest.mark.xdist_group("group_2")
def test_greeting_no_name() -> None:
    """Test greeting with no name"""
    with pytest.raises(ValueError):
        greeting("")
