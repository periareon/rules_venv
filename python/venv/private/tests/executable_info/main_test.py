"""A test for `PyExecutableInfo` tests."""

import unittest

from python.venv.private.tests.executable_info.lib import GREETING


class GreetingTest(unittest.TestCase):
    """Test the greeting."""

    def test_greeting(self) -> None:
        """Ensure the greeting is correct."""
        self.assertEqual(GREETING, "La-Li-Lu-Le-Lo")


if __name__ == "__main__":
    unittest.main()
