"""Tests to provide coverage used to exercise the coverage functionality of `py_pytest_test`"""

import pytest

from python.pytest.private.tests.with_args import lib, lib_testonly


def test_divide() -> None:
    """Test division"""
    assert lib_testonly
    assert lib.divide(10, 2) == 5


def test_divide_by_zero() -> None:
    """Test attempting to divide by 0"""
    with pytest.raises(ValueError) as e_info:
        lib.divide(3, 0)
        assert str(e_info) == "Cannot divide by 0"


def test_sum() -> None:
    """Test addition"""
    assert lib.submod.sum(128, 128) == 256


def test_greeting() -> None:
    """Test greeting"""
    assert lib.submod.greeting("Mars") == "Hello, Mars!"


def test_greeting_no_name() -> None:
    """Test greeting with no name"""
    with pytest.raises(ValueError):
        lib.submod.greeting("")


def test_custom_arg(custom_arg: str) -> None:
    """Test that custom command line arguments are assigned to expected values"""
    assert custom_arg == "La-Li-Lu-Le-Lo"
