"""Test fibonacci.py"""

import unittest

from python.venv.private.tests.test_with_dep.fibonacci import fibonacci


class FibonacciTest(unittest.TestCase):
    """Tests for the fibonacci module."""

    def test_sequence(self) -> None:
        """Test Fibonacci sequences"""
        self.assertEqual(fibonacci(11), 144)
        self.assertEqual(fibonacci(12), 233)
        self.assertEqual(fibonacci(13), 377)

if __name__ == "__main__":
    unittest.main()
