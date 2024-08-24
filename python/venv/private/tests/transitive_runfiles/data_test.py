"""Test that data in transitive libraries are accessible"""

import unittest

from python.venv.private.tests.transitive_runfiles import data


class TransitiveDataAccessTests(unittest.TestCase):
    """Test that transitive runfiles are available in executables."""

    def test_data(self) -> None:
        """Test access to source data."""
        runfiles = data.create_runfiles()

        self.assertEqual("La-Li-Lu-Le-Lo", data.get_data(runfiles))

    def test_generated_data(self) -> None:
        """Test access to generated data."""
        runfiles = data.create_runfiles()

        self.assertEqual("Big Boss", data.get_generated_data(runfiles))


if __name__ == "__main__":
    unittest.main()
