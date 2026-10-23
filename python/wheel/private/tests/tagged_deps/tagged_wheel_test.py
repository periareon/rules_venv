"""Tests of the requirements a wheel records for tagged and untagged dependencies."""

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


class TaggedWheelTests(unittest.TestCase):
    """Unit tests for the `tagged` test wheel."""

    def test_requires_dist(self) -> None:
        """A dependency is required by its tag, else its `.dist-info`, else its label.

        Constraints apply to all three, however their names are spelled.
        """
        runfiles = Runfiles.Create()
        if not runfiles:
            raise OSError("Failed to locate runfiles.")

        wheel = _rlocation(runfiles, os.environ["WHEEL"])
        wheel_dir = Path(
            tempfile.mkdtemp(prefix="wheel-", dir=os.environ["TEST_TMPDIR"])
        )
        with zipfile.ZipFile(wheel) as zip_ref:
            zip_ref.extractall(wheel_dir)

        metadata_files = list(wheel_dir.glob("*.dist-info/METADATA"))
        self.assertEqual(
            1, len(metadata_files), f"Expected one METADATA: {metadata_files}"
        )

        requires_dists = [
            line.partition(" ")[2].strip()
            for line in metadata_files[0].read_text(encoding="utf-8").splitlines()
            if line.startswith("Requires-Dist: ")
        ]

        self.assertListEqual(
            ["Dist_Info_Pkg~=3.0", "Fancy-Pkg>=1.0.0", "plain<2"], requires_dists
        )


if __name__ == "__main__":
    unittest.main()
