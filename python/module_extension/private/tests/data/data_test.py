"""Tests for `py_cc_extension.data`."""

import os
import platform
import unittest
from pathlib import Path

from python.runfiles import Runfiles

from python.module_extension.private.tests.data import with_data  # type: ignore


class DataTest(unittest.TestCase):
    """Test Class."""

    def _rlocation(self, name: str) -> Path:
        runfiles = Runfiles.Create()
        assert runfiles is not None

        # TODO: https://github.com/periareon/rules_venv/issues/37
        source_repo = None
        if platform.system() == "Windows":
            source_repo = ""

        workspace = os.environ["TEST_WORKSPACE"]
        path = runfiles.Rlocation(
            f"{workspace}/python/module_extension/private/tests/data/{name}",
            source_repo,
        )
        assert path is not None
        return Path(path)

    def test_extension_loads(self) -> None:
        """The extension itself still imports."""
        self.assertEqual(with_data.greet(), "hello")

    def test_extension_data(self) -> None:
        """`data` on the extension itself is in the runfiles."""
        self.assertTrue(self._rlocation("extension_data.txt").exists())

    def test_dep_data(self) -> None:
        """`data` on a `cc_library` in `deps` is in the runfiles."""
        self.assertTrue(self._rlocation("dep_data.txt").exists())


if __name__ == "__main__":
    unittest.main()
