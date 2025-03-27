"""Unit tests for zipapp embedded arguments."""

import os
import platform
import unittest
from pathlib import Path

from python.runfiles import Runfiles


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


class UnitTests(unittest.TestCase):
    """Unit Tests"""

    runfiles: Runfiles

    @classmethod
    def setUpClass(cls) -> None:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles.")

        cls.runfiles = runfiles

        return super().setUpClass()

    def test_from_binary(self) -> None:
        """Test the output of a zipapp with binary inherited args."""
        output = _rlocation(self.runfiles, os.environ["FROM_BINARY"])

        assert output.read_text(encoding="utf-8").strip() == "Hello, From Binary"

    def test_from_zipapp(self) -> None:
        """Test the output of a zipapp embedded args."""
        output = _rlocation(self.runfiles, os.environ["FROM_ZIPAPP"])

        assert output.read_text(encoding="utf-8").strip() == "Hello, From Zipapp"


if __name__ == "__main__":
    unittest.main()
