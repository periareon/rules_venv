"""Tests to provide coverage used to excersize the coverage functionality of `py_pytest_test`"""

import pytest

import python.pytest.private.tests.coverage.multi_file.lib as coverage


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
