"""Test for interactions with Bazel's TEST_TMPDIR"""

import os
from pathlib import Path


def test_tempdir(tmpdir: Path) -> None:
    """Test that temp directories are written to the Bazel TEST_TMPDIR"""
    bazel_test_tmpdir = Path(os.environ["TEST_TMPDIR"])

    assert Path(tmpdir).is_relative_to(
        bazel_test_tmpdir
    ), f"pytest.tmpdir is not relative to TEST_TMPDIR.\npytest: {tmpdir}\nbazel: {bazel_test_tmpdir}"
