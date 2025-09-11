"""Tests to provide coverage used to excersize the coverage functionality of `py_pytest_test`"""

import pytest

import python.pytest.private.tests.coverage.split_collection.lib as coverage


def test_divide() -> None:
    """Test division"""
    assert coverage.divide(10, 2) == 5


def test_divide_by_zero() -> None:
    """Test attempting to divide by 0"""
    with pytest.raises(ValueError) as e_info:
        coverage.divide(3, 0)
    assert e_info.match(r"Cannot divide by 0")
