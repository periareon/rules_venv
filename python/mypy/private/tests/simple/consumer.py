"""Testcases for mypy to test correctly typed libraries."""

import unittest

from python.mypy.private.tests.simple.thrice import thrice


class UnitTests(unittest.TestCase):
    """Unit tests"""

    @staticmethod
    def increment(i: int) -> int:
        """Increment `i` by 1."""
        return i + 1

    def test_thrice(self) -> None:
        """Make use of an external function so mypy is forced to resolve types."""
        self.assertEqual(thrice(3, UnitTests.increment), 6)


if __name__ == "__main__":
    unittest.main()
