"""Test that directories created with ctx.actions.declare_directory are accessible via runfiles."""

import os
import platform
import unittest
from pathlib import Path

from python.runfiles import Runfiles


def _rlocationpath_env(name: str) -> str:
    """Get `rlocationpath` values from the environment.

    Bazel wraps `rlocationpath` values with `'` characters which are required
    to be stripped if they're to be used by the Runfiles API.

    Args:
        name: The name of the environment variable.

    Returns:
        The value of the environment variable.
    """
    return os.environ[name].strip("'")


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runfile.
    """
    # TODO: https://github.com/periareon/rules_venv/issues/37
    source_repo = None
    if platform.system() == "Windows":
        source_repo = ""
    runfile = runfiles.Rlocation(rlocationpath, source_repo)
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


class DataDirectoryAccessTests(unittest.TestCase):
    """Test that directories created with declare_directory are accessible via runfiles."""

    runfiles: Runfiles

    @classmethod
    def setUpClass(cls) -> None:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles.")

        cls.runfiles = runfiles

        return super().setUpClass()

    def test_nested_file_in_directory(self) -> None:
        """Test access to a nested file within a declared directory."""
        # Get the directory path from runfiles
        dir_path = _rlocation(self.runfiles, _rlocationpath_env("DATA_DIR"))

        # Verify the directory exists
        self.assertTrue(dir_path.exists(), f"Directory does not exist: {dir_path}")
        self.assertTrue(dir_path.is_dir(), f"Path is not a directory: {dir_path}")

        # Navigate to the nested file
        nested_file = dir_path / "subdir" / "nested" / "data.txt"

        # Verify the nested file exists
        self.assertTrue(
            nested_file.exists(), f"Nested file does not exist: {nested_file}"
        )

        # Read and assert on the content
        text = nested_file.read_text(encoding="utf-8")
        self.assertEqual("Hello from nested directory!", text.strip())

    def test_top_level_file_in_directory(self) -> None:
        """Test access to a top-level file within a declared directory."""
        # Get the directory path from runfiles
        dir_path = _rlocation(self.runfiles, _rlocationpath_env("DATA_DIR"))

        # Access the top-level file
        top_file = dir_path / "top_level.txt"

        # Verify the file exists
        self.assertTrue(top_file.exists(), f"Top-level file does not exist: {top_file}")

        # Read and assert on the content
        text = top_file.read_text(encoding="utf-8")
        self.assertEqual("Top Level Content", text.strip())


if __name__ == "__main__":
    unittest.main()
