"""Pytest test code
"""

import subprocess
import sys
import unittest


class PytestTests(unittest.TestCase):
    """Test that pytest and pytest plugins are configured correctly."""

    def assert_text_contains(self, text: str, container: str) -> None:
        """Assert that a string is present in a larger string."""
        assert (
            text in container
        ), f"`{text}` was not found in text:\n```\n{container}\n```"

    def test_module_script(self) -> None:
        """Show that modules can be used as scripts"""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--help"],
            encoding="utf-8",
            capture_output=True,
            check=True,
        )

        self.assert_text_contains(
            "[options] [file_or_dir] [file_or_dir] [...]", result.stdout
        )

    def test_extensions(self) -> None:
        """Show that pytest extensions are usable."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--help"],
            encoding="utf-8",
            capture_output=True,
            check=True,
        )

        self.assert_text_contains(
            "coverage reporting with distributed testing support", result.stdout
        )


if __name__ == "__main__":
    unittest.main()
