"""# Pytest

Bazel rules for the python test framework [Pytest](https://docs.pytest.org/en/stable/).
"""

load(
    "//python/pytest/private:pytest.bzl",
    _current_py_pytest_toolchain = "current_py_pytest_toolchain",
    _py_pytest_test = "py_pytest_test",
    _py_pytest_test_suite = "py_pytest_test_suite",
    _py_pytest_toolchain = "py_pytest_toolchain",
)

current_py_pytest_toolchain = _current_py_pytest_toolchain
py_pytest_test = _py_pytest_test
py_pytest_test_suite = _py_pytest_test_suite
py_pytest_toolchain = _py_pytest_toolchain
