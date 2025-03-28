"""Tests to provide coverage used to excersize the coverage functionality of `py_pytest_test`"""

import pytest

import python.pytest.private.tests.coverage.empty_config.lib as coverage


def test_divide() -> None:
    """Test division"""
    assert coverage.divide(10, 2) == 5


def test_divide_by_zero() -> None:
    """Test attempting to divide by 0"""
    with pytest.raises(ValueError) as e_info:
        coverage.divide(3, 0)
    assert e_info.match(r"Cannot divide by 0")


def test_sum() -> None:
    """Test addition"""
    assert coverage.submod.sum(128, 128) == 256


def test_greeting() -> None:
    """Test greeting"""
    assert coverage.submod.greeting("Mars") == "Hello, Mars!"


def test_greeting_no_name() -> None:
    """Test greeting with no name"""
    with pytest.raises(ValueError):
        coverage.submod.greeting("")
