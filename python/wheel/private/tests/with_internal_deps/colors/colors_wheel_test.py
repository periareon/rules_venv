"""Unit tests."""

import os
import platform
import tempfile
import unittest
import zipfile
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


class WheelTests(unittest.TestCase):
    """Unit tests for the `with_internal_deps` test wheel."""

    runfiles: Runfiles

    @classmethod
    def setUpClass(cls) -> None:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles.")

        cls.runfiles = runfiles

        return super().setUpClass()

    def setUp(self) -> None:
        self.wheel = _rlocation(self.runfiles, os.environ["WHEEL"])
        self.wheel_dir = Path(
            tempfile.mkdtemp(prefix="wheel-", dir=os.environ["TEST_TMPDIR"])
        )
        with zipfile.ZipFile(self.wheel) as zip_ref:
            zip_ref.extractall(self.wheel_dir)

        return super().setUp()

    def test_structure(self) -> None:
        """Test the wheel has a structure which correctly includes it's dependencies."""
        for name in ["red", "green", "blue", "colors"]:
            file = (
                self.wheel_dir
                / f"python/wheel/private/tests/with_internal_deps/{name}/{name}.py"
            )
            self.assertTrue(file.exists(), file)

        for name in ["red", "blue"]:
            file = (
                self.wheel_dir
                / f"python/wheel/private/tests/with_internal_deps/{name}/data.txt"
            )
            self.assertTrue(file.exists(), file)
            self.assertEqual(file.read_text(encoding="utf-8").strip(), name)


if __name__ == "__main__":
    unittest.main()
