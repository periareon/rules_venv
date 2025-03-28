"""Test sharding from Bazel in pytest.

Note that there is no way to control what function is tested in a specific shard.
"""

import os


def test_shard_a():
    assert "TEST_SHARD_INDEX" in sorted(os.environ.keys())


def test_shard_b():
    assert "TEST_SHARD_INDEX" in sorted(os.environ.keys())
