"""# py_pylint_toolchain"""

load(
    "//python/pylint/private:pylint_toolchain.bzl",
    _py_pylint_toolchain = "py_pylint_toolchain",
)

py_pylint_toolchain = _py_pylint_toolchain
