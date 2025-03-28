"""Tests confirming interactions TemplateVariableInfo works."""

import os


def test_expanded_var() -> None:
    """Test variable expansions in env vars."""
    assert os.environ["EXPANDED_VAR"] == "Hello World!"
