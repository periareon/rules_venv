"""A script which consumes imports through import paths shared by multiple imports.

All tests in `rules_venv` live under `python.venv.private.tests` and the
`python.within_second_python.py_dep` packages uses the `imports` attribute to
expose this module at that location.
"""

import unittest

from python.venv.private.tests.import_duplicates.consumer import consumer


class ConsumerTests(unittest.TestCase):
    """Test class"""

    def test_greeting(self) -> None:
        """Test greeting"""
        self.assertEqual(
            consumer.generate_greeting_followup("Boss"), "Hallo, Boss!! How are you?"
        )

    def test_data(self) -> None:
        """Test data"""
        self.assertEqual(consumer.load_data(), "La-Li-Lu-Le-Lo")


if __name__ == "__main__":
    unittest.main()
