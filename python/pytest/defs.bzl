"""# Pytest

Bazel rules for the python test framework [Pytest](https://docs.pytest.org/en/stable/).
"""

load(
    ":current_py_pytest_toolchain.bzl",
    _current_py_pytest_toolchain = "current_py_pytest_toolchain",
)
load(
    ":py_pytest_test.bzl",
    _py_pytest_test = "py_pytest_test",
)
load(
    ":py_pytest_test_suite.bzl",
    _py_pytest_test_suite = "py_pytest_test_suite",
)
load(
    ":py_pytest_toolchain.bzl",
    _py_pytest_toolchain = "py_pytest_toolchain",
)

current_py_pytest_toolchain = _current_py_pytest_toolchain
py_pytest_test = _py_pytest_test
py_pytest_test_suite = _py_pytest_test_suite
py_pytest_toolchain = _py_pytest_toolchain
