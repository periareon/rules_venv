"""# current_py_pytest_toolchain"""

load(
    "//python/pytest/private:pytest.bzl",
    _current_py_pytest_toolchain = "current_py_pytest_toolchain",
)

current_py_pytest_toolchain = _current_py_pytest_toolchain
