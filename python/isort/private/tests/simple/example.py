"""A python source file to demonstrate isort sorting all kinds of imports

Due to the use of repo relative paths we only see `toml` as the only third
party package (as denoted by it being separated by empty lines).
"""

import os
import unittest
from pathlib import Path

import tomlkit

import python.isort.private.tests.simple.first_party_1
import python.isort.private.tests.simple.first_party_3 as first_party_3  # pylint: disable=consider-using-from-import
from python.isort.private.tests.simple.first_party_2 import (
    assert_equal as assert_equal_2,
)

TEST_PATH = "/tmp/test/isort"


class ExampleTests(unittest.TestCase):
    """Example test case"""

    def test_first_party(self) -> None:
        """Execute some code using first party packages"""
        python.isort.private.tests.simple.first_party_1.assert_equal(
            os.path.basename(TEST_PATH), str(Path(TEST_PATH).name)
        )
        first_party_3.assert_equal(
            os.path.basename(TEST_PATH), str(Path(TEST_PATH).name)
        )
        assert_equal_2(os.path.basename(TEST_PATH), str(Path(TEST_PATH).name))

    def test_third_party(self) -> None:
        """Execute some code using third party packages"""
        assert "tomlkit" == tomlkit.__name__


if __name__ == "__main__":
    unittest.main()
