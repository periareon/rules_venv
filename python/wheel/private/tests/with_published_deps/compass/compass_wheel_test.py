"""Unit tests."""

import os
import platform
import tempfile
import unittest
import zipfile
from pathlib import Path

from python.runfiles import Runfiles  # type: ignore


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
    """Unit tests for the `with_published_deps` test wheel."""

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

    def test_constraints(self) -> None:
        """Test the wheel has recorded all external requirements and applied constraints."""
        metadata_file = None
        for root, _, filenames in os.walk(self.wheel_dir):
            for filename in filenames:
                if filename == "METADATA":
                    self.assertIsNone(metadata_file, "Found two METADATA files")
                    metadata_file = Path(root) / filename

        assert metadata_file is not None

        requires_dists = []
        for line in metadata_file.read_text(encoding="utf-8").splitlines():
            if not line.startswith("Requires-Dist: "):
                continue
            _, _, requirement = line.partition(" ")
            requires_dists.append(requirement.strip())

        expected = [
            # From core wheel
            "black>=25.0.0",
            # From west
            "numpy>=2.0.0",
            # From north
            "twine",
        ]

        self.assertListEqual(expected, requires_dists)


if __name__ == "__main__":
    unittest.main()
