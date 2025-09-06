"""Test that runfiles with spaces are accessible"""

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
        The requested runifle.
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


class TransitiveDataAccessTests(unittest.TestCase):
    """Test that runfiles with spaces are available in executables."""

    runfiles: Runfiles

    @classmethod
    def setUpClass(cls) -> None:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles.")

        cls.runfiles = runfiles

        return super().setUpClass()

    def test_data(self) -> None:
        """Test access to source data."""
        path = _rlocation(self.runfiles, _rlocationpath_env("DATA_FILE"))

        text = path.read_text(encoding="utf-8")

        self.assertEqual("La-Li-Lu-Le-Lo", text.strip())

    def test_generated_data(self) -> None:
        """Test access to generated data."""
        path = _rlocation(self.runfiles, _rlocationpath_env("GENERATED_DATA"))

        text = path.read_text(encoding="utf-8")

        self.assertEqual("LA-LI-LU-LE-LO", text.strip())


if __name__ == "__main__":
    unittest.main()
