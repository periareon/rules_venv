"""Test sharding from Bazel in pytest.

Note that there is no way to control what function is tested in a specific shard.
"""

import os


def test_shard_a() -> None:
    """A test to run on an available shard."""
    assert "TEST_SHARD_INDEX" in sorted(os.environ)


def test_shard_b() -> None:
    """A test to run on an available shard."""
    assert "TEST_SHARD_INDEX" in sorted(os.environ)
