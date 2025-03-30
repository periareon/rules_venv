"""Unit tests to show simple interactions with PyO3 modules."""

import unittest

# pylint: disable-next=no-name-in-module
from python.module_extension.private.tests.compilation_modes.string_sum_current import (  # type: ignore
    sum_as_string,
)


class StringSumTest(unittest.TestCase):
    """Test Class."""

    def test_sum_as_string(self) -> None:
        """Simple test of C/C++ defined functions."""

        result = sum_as_string(1337, 42)
        self.assertIsInstance(result, str)
        self.assertEqual("1379", result)


if __name__ == "__main__":
    unittest.main()
