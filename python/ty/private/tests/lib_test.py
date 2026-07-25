"""A typed test."""

import unittest

from python.ty.private.tests.lib import add

# Aliasing ``unittest.TestCase`` before subclassing sidesteps a ``salsa``
# dependency-cycle panic in ``ty 0.0.63`` (astral-sh/ty) triggered when
# resolving the enum-based metaclass chain reachable through the bundled
# stdlib. At runtime this is still a real ``TestCase`` — unittest
# discovery, ``self.assertEqual``, and ``unittest.main`` all work.
_TestCase = unittest.TestCase


class AddTest(_TestCase):
    """Tests for add."""

    def test_add(self) -> None:
        """Verify add returns the sum."""
        self.assertEqual(add(1, 2), 3)


if __name__ == "__main__":
    unittest.main()
