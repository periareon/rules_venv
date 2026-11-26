"""Tests for `py_cc_extension.dynamic_deps`."""

import unittest

from python.module_extension.private.tests.dynamic_deps import (  # type: ignore
    increment_first,
    increment_second,
)


class DynamicDepsTest(unittest.TestCase):
    """Test Class."""

    def test_extensions_share_one_counter(self) -> None:
        """Both extensions load the counter from the same shared library."""
        self.assertEqual(increment_first.increment(), 1)
        self.assertEqual(increment_second.increment(), 2)


if __name__ == "__main__":
    unittest.main()
