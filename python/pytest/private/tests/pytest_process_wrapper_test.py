"""Tests for the pytest_process_wrapper.py process wrapper"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from python.runfiles import runfiles

import python.pytest.private.pytest_process_wrapper as process_wrapper

WORKSPACE_NAME = "rules_venv_pytest"


class TestRunPytestArgParsing(unittest.TestCase):
    """Test cases for `pytest_process_wrapper.parse_args`"""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(dir=os.environ.get("TEST_TMPDIR", None)))
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        test_src = self.temp_dir / WORKSPACE_NAME / "src.py"
        test_src.parent.mkdir(exist_ok=True, parents=True)
        test_src.write_text("", encoding="utf-8")

        return super().setUp()

    def tearDown(self) -> None:
        shutil.rmtree(str(self.temp_dir))
        return super().tearDown()

    def test_normal(self) -> None:
        """Test parsing expected args"""
        args = [
            "--cov-config",
            "tmp/coveragerc",
            "--pytest-config",
            "tmp/pytest.toml",
            "--src",
            f"{WORKSPACE_NAME}/src.py",
            "--",
            # Pytest args would go here
        ]

        (self.temp_dir / "tmp").mkdir(exist_ok=True, parents=True)
        (self.temp_dir / "tmp/coveragerc").write_bytes(b"")
        (self.temp_dir / "tmp/pytest.toml").write_bytes(b"")

        with mock.patch.dict(
            os.environ,
            {
                "RUNFILES_DIR": str(self.temp_dir),
                "TEST_WORKSPACE": WORKSPACE_NAME,
            },
            clear=True,
        ):
            mock_runfiles = runfiles.Create()
            assert mock_runfiles is not None
            parsed_args = process_wrapper.parse_args(mock_runfiles, args)

            self.assertListEqual(parsed_args.pytest_args, [])

    def test_no_trailing_delimiter(self) -> None:
        """Test that the delimiter between process wrapper args and pytest args are flexible"""
        args = [
            "--cov-config",
            "tmp/coveragerc",
            "--pytest-config",
            "tmp/pytest.toml",
            "--src",
            f"{WORKSPACE_NAME}/src.py",
            # The pytest args delimiter is allowed to be missing
            # "--""
        ]

        (self.temp_dir / "tmp").mkdir(exist_ok=True, parents=True)
        (self.temp_dir / "tmp/coveragerc").write_bytes(b"")
        (self.temp_dir / "tmp/pytest.toml").write_bytes(b"")

        with mock.patch.dict(
            os.environ,
            {
                "RUNFILES_DIR": str(self.temp_dir),
                "TEST_WORKSPACE": WORKSPACE_NAME,
            },
            clear=True,
        ):
            mock_runfiles = runfiles.Create()
            assert mock_runfiles is not None
            parsed_args = process_wrapper.parse_args(mock_runfiles, args)

            self.assertListEqual(parsed_args.pytest_args, [])

    def test_pytest_args(self) -> None:
        """Test parsing extra pytest args"""
        args = [
            "--cov-config",
            "tmp/coveragerc",
            "--pytest-config",
            "tmp/pytest.toml",
            "--src",
            f"{WORKSPACE_NAME}/src.py",
            "--",
        ]

        (self.temp_dir / "tmp").mkdir(exist_ok=True, parents=True)
        (self.temp_dir / "tmp/coveragerc").write_bytes(b"")
        (self.temp_dir / "tmp/pytest.toml").write_bytes(b"")

        pytest_args = [
            "--log-level",
            "DEBUG",
            "-v",
            "--duration-min",
            "0.005",
        ]

        with mock.patch.dict(
            os.environ,
            {
                "RUNFILES_DIR": str(self.temp_dir),
                "TEST_WORKSPACE": WORKSPACE_NAME,
            },
            clear=True,
        ):
            mock_runfiles = runfiles.Create()
            assert mock_runfiles is not None
            parsed_args = process_wrapper.parse_args(mock_runfiles, args + pytest_args)

            self.assertListEqual(parsed_args.pytest_args, pytest_args)

    def test_numprocesses_rejected(self) -> None:
        """Ensure users are not allowed to pass `numprocesses` (`-n`) directly to pytest"""
        args = [
            "--cov-config",
            "tmp/coveragerc",
            "--pytest-config",
            "tmp/pytest.toml",
            "--src",
            f"{WORKSPACE_NAME}/src.py",
            "--",
            "-n",
            "4",
        ]

        (self.temp_dir / "tmp").mkdir(exist_ok=True, parents=True)
        (self.temp_dir / "tmp/coveragerc").write_bytes(b"")
        (self.temp_dir / "tmp/pytest.toml").write_bytes(b"")

        with mock.patch.dict(
            os.environ,
            {
                "RUNFILES_DIR": str(self.temp_dir),
                "TEST_WORKSPACE": WORKSPACE_NAME,
            },
            clear=True,
        ):
            mock_runfiles = runfiles.Create()
            assert mock_runfiles is not None
            with self.assertRaises(SystemExit):
                process_wrapper.parse_args(mock_runfiles, args)


if __name__ == "__main__":
    unittest.main()
