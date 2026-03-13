"""Import tests"""

import unittest


class ImportsTest(unittest.TestCase):
    """Test that packages are importable via the `imports` attribute."""

    def test_alpha(self) -> None:
        """Test alpha imports."""
        # pylint: disable-next=import-outside-toplevel
        import alpha

        self.assertEqual(alpha.ALPHA, "alpha")

    def test_bravo(self) -> None:
        """Test bravo imports."""
        # pylint: disable-next=import-outside-toplevel
        import bravo

        self.assertEqual(bravo.BRAVO, "bravo")


if __name__ == "__main__":
    unittest.main()
