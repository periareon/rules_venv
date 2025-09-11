"""Test interactions with modified environment variables"""

import os
import pathlib


def test_user_home_expand() -> None:
    """Test the use of `pathlib.Path.home` as it's behavior changed in py3.11"""
    test_tmpdir = pathlib.Path(os.environ["TEST_TMPDIR"])
    home_dir = str(pathlib.Path.home())
    assert len(home_dir) > 0
    assert str(test_tmpdir / "home") == home_dir
