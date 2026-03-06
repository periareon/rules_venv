"""# py_ruff_toolchain"""

load(
    "//python/ruff/private:ruff_toolchain.bzl",
    _py_ruff_toolchain = "py_ruff_toolchain",
)

py_ruff_toolchain = _py_ruff_toolchain
