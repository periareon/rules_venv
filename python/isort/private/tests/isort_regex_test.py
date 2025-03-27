"""Tests for ensuring source files have correctly ordered imports"""

import json
import os
import unittest
from pathlib import Path

from python.runfiles import Runfiles


class IsortRegexTest(unittest.TestCase):
    """Test class"""

    def assert_text_contains(self, text: str, container: str) -> None:
        """Assert that a string is present in a larger string."""
        assert (
            text in container
        ), f"`{text}` was not found in text:\n```\n{container}\n```"

    def test_source(self) -> None:
        """Test import order in source file."""
        runfiles = Runfiles.Create()
        assert runfiles is not None

        rlocationpath = os.environ["ISORT_REGEX_SRC"]
        runfile = runfiles.Rlocation(rlocationpath)
        assert runfile is not None, f"Failed to find runfile: {rlocationpath}"

        expected = json.loads(os.environ["ISORT_REGEX_EXPECTATION"])
        content = Path(runfile).read_text(encoding="utf-8")

        self.assert_text_contains(expected, content)


if __name__ == "__main__":
    unittest.main()
