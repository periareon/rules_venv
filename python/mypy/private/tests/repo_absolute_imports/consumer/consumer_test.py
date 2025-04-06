"""Demonstrate mypy can validate imports from repo absolute paths."""

import unittest

from python.mypy.private.tests.repo_absolute_imports.consumer.consumer import (
    color_name,
    stringify_numbers,
)


class UnitTests(unittest.TestCase):
    """Unit tests"""

    def test_color_name(self) -> None:
        """Test color_name."""
        assert color_name(1) == "red"
        assert color_name(2) == "green"
        assert color_name(3) == "blue"

    def test_stringify_numbers(self) -> None:
        """Test stringify_numbers."""
        assert stringify_numbers([1, None, 3]) == ["1", "None", "3"]
