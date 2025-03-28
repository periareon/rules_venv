"""Pytest configure functionality"""

from typing import Any

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add additional command line flags to pytest"""
    parser.addoption("--custom_arg", action="store")


@pytest.fixture
def custom_arg(request: pytest.FixtureRequest) -> Any:
    """Expose custom command line values as fixtures"""
    return request.config.getoption("--custom_arg")
