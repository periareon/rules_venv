"""# py_mypy_toolchain"""

load(
    "//python/mypy/private:mypy_toolchain.bzl",
    _py_mypy_toolchain = "py_mypy_toolchain",
)

py_mypy_toolchain = _py_mypy_toolchain
