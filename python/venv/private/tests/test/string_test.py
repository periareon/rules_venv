"""Python example code."""

import unittest


class TestStringMethods(unittest.TestCase):
    """Test basic functionality of Python strings."""

    def test_upper(self) -> None:
        """Test the `str.upper` method"""
        self.assertEqual("foo".upper(), "FOO")

    def test_isupper(self) -> None:
        """Test the `str.isupper` method."""
        self.assertTrue("FOO".isupper())
        self.assertFalse("Foo".isupper())

    def test_split(self) -> None:
        """Test the `str.split` method."""
        s = "hello world"
        self.assertEqual(s.split(), ["hello", "world"])
        # check that s.split fails when the separator is not a string
        with self.assertRaises(TypeError):
            s.split(2)  # type: ignore


if __name__ == "__main__":
    unittest.main()
