"""A typed test."""

import unittest

from python.ty.private.tests.lib import add


class AddTest(unittest.TestCase):
    """Tests for add."""

    def test_add(self) -> None:
        """Verify add returns the sum."""
        self.assertEqual(add(1, 2), 3)
