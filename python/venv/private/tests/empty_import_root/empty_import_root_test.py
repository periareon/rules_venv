"""Tests that an import root survives having nothing staged under it.

`site` silently drops a `.pth` line whose directory does not exist, so a
root is only on `sys.path` if something made the directory. Nothing does
that on the way in -- Bazel stages files, not the directories between
them -- which leaves the root's presence depending on whether some file
happened to land under it.

That matters to anything that writes into the venv after it is built. A
caller that replaces a dependency's sources with something cheaper, as
the mypy rules do, empties the root it was going to write into, and the
write then lands somewhere `sys.path` no longer names.
"""

import sys
import unittest
from pathlib import Path


class EmptyImportRootTest(unittest.TestCase):
    """Whether a root with no sources under it reaches `sys.path`."""

    def test_the_root_is_on_sys_path(self) -> None:
        """The venv names the root, so the venv is what has to create it."""
        roots = [Path(entry).name for entry in sys.path]

        self.assertIn("empty_root", roots)

    def test_the_root_is_a_directory(self) -> None:
        """An entry `site` kept is one that resolves, not just a string."""
        matches = [
            Path(entry) for entry in sys.path if Path(entry).name == "empty_root"
        ]

        self.assertTrue(matches, "`empty_root` is not on `sys.path`")
        for match in matches:
            self.assertTrue(match.is_dir(), f"Not a directory: {match}")


if __name__ == "__main__":
    unittest.main()
