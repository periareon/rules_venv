"""# py_pytest_toolchain"""

load(
    "//python/pytest/private:pytest.bzl",
    _py_pytest_toolchain = "py_pytest_toolchain",
)

py_pytest_toolchain = _py_pytest_toolchain
