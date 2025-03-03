"""A small test script"""

import os
import platform
import unittest
from pathlib import Path

from python.runfiles import Runfiles  # type: ignore


def rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
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


class AspectConsumerTest(unittest.TestCase):
    """Test the outputs of a `py_venv_binary` created in an aspect."""

    def test_output(self) -> None:
        """Test the action output exists and is formed correctly."""
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles.")

        aspect_output = rlocation(runfiles, os.environ["ASPECT_ACTION_OUTPUT"])

        self.assertEqual("La-Li-Lu-Le-Lo", aspect_output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
