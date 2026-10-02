"""Tests for `RULES_VENV_EXTRACT_ROOT` and `RULES_PYTHON_EXTRACT_ROOT`."""

import json
import os
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path

from python.runfiles import Runfiles

_ROOT_VARS = ("RULES_VENV_EXTRACT_ROOT", "RULES_PYTHON_EXTRACT_ROOT")

_VENV_RELATIVE_PATH = Path("_main/python/venv/private/tests/extract_root/where.venv")
"""Where the `where` binary's venv lands under an extract root."""

_STAMP_NAME = "rules_venv.stamp.json"


def _run_where(env: dict[str, str]) -> Path:
    """Run the `where` binary and return the `sys.executable` it reported."""
    runfiles = Runfiles.Create()
    if not runfiles:
        raise OSError("Failed to locate runfiles.")

    # TODO: https://github.com/periareon/rules_venv/issues/37
    source_repo = None
    if platform.system() == "Windows":
        source_repo = ""

    binary = runfiles.Rlocation(os.environ["WHERE_RLOCATIONPATH"], source_repo)
    if not binary:
        raise FileNotFoundError(os.environ["WHERE_RLOCATIONPATH"])

    child_env = {
        key: value for key, value in os.environ.items() if key not in _ROOT_VARS
    }
    child_env.update(env)

    result = subprocess.run(
        [binary],
        env=child_env,
        check=True,
        capture_output=True,
        text=True,
    )

    return Path(result.stdout.strip())


class ExtractRootTest(unittest.TestCase):
    """Tests for the extract root behavior of the process wrapper."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(dir=os.environ.get("TEST_TMPDIR")))

    def test_rules_venv_extract_root(self) -> None:
        """A root gives a predictable, persistent, reusable venv."""
        root = self.tmp / "venv_root"
        venv_dir = root / _VENV_RELATIVE_PATH

        interpreter = _run_where({"RULES_VENV_EXTRACT_ROOT": str(root)})

        self.assertTrue(interpreter.is_relative_to(venv_dir), interpreter)
        self.assertTrue(interpreter.exists(), interpreter)

        stamp = venv_dir / _STAMP_NAME
        built = stamp.stat().st_mtime_ns

        # A second launch reuses the venv rather than rebuilding it.
        self.assertEqual(
            interpreter, _run_where({"RULES_VENV_EXTRACT_ROOT": str(root)})
        )
        self.assertEqual(built, stamp.stat().st_mtime_ns)

    def test_rules_python_extract_root(self) -> None:
        """`RULES_PYTHON_EXTRACT_ROOT` is honored on its own."""
        root = self.tmp / "python_root"

        interpreter = _run_where({"RULES_PYTHON_EXTRACT_ROOT": str(root)})

        self.assertTrue(
            interpreter.is_relative_to(root / _VENV_RELATIVE_PATH), interpreter
        )

    def test_rules_venv_root_takes_priority(self) -> None:
        """`RULES_VENV_EXTRACT_ROOT` wins when both variables are set."""
        venv_root = self.tmp / "venv_root"
        python_root = self.tmp / "python_root"

        interpreter = _run_where(
            {
                "RULES_VENV_EXTRACT_ROOT": str(venv_root),
                "RULES_PYTHON_EXTRACT_ROOT": str(python_root),
            }
        )

        self.assertTrue(
            interpreter.is_relative_to(venv_root / _VENV_RELATIVE_PATH), interpreter
        )
        self.assertFalse(python_root.exists(), python_root)

    def test_stale_venv_is_rebuilt(self) -> None:
        """A venv whose stamp no longer matches is replaced in place."""
        root = self.tmp / "venv_root"
        stamp = root / _VENV_RELATIVE_PATH / _STAMP_NAME
        env = {"RULES_VENV_EXTRACT_ROOT": str(root)}

        interpreter = _run_where(env)
        original = json.loads(stamp.read_text(encoding="utf-8"))
        stamp.write_text(json.dumps(dict(original, key="stale")), encoding="utf-8")

        self.assertEqual(interpreter, _run_where(env))
        self.assertEqual(original, json.loads(stamp.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
