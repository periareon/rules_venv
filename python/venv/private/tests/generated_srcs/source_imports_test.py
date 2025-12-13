"""Represent interactions with generated."""

import io
import sys
import unittest

from source_imports import say_hello


class GreetingTests(unittest.TestCase):
    """Test Class."""

    def test_hello(self) -> None:
        """A simple test to invoke library code."""

        captured = io.StringIO()
        sys_stdout = sys.stdout
        try:
            sys.stdout = captured
            say_hello("World")
        finally:
            sys.stdout = sys_stdout

        self.assertIn("Hello, World", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
