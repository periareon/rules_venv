"""Entrypoint listed before its sibling in `srcs`."""

import unittest

from python.venv.private.tests.inferred_main import shared


class InferredMainTest(unittest.TestCase):
    """Test cases"""

    def test_shared(self) -> None:
        """Test case"""
        self.assertEqual(shared.MESSAGE, "La-Li-Lu-Le-Lo.")


if __name__ == "__main__":
    unittest.main()
