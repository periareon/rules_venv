"""Tests for `py_cc_extension.stripped`."""

import unittest

from python.module_extension.private.tests.stripped import (  # type: ignore
    string_sum_stripped,
)


class StrippedTest(unittest.TestCase):
    """Test Class."""

    def test_stripped_extension_loads(self) -> None:
        """The stripped shared library is still a working module."""
        self.assertEqual(string_sum_stripped.sum_as_string(1, 2), "3")


if __name__ == "__main__":
    unittest.main()
