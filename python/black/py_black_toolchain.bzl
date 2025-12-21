"""# py_black_toolchain"""

load(
    "//python/black/private:black_toolchain.bzl",
    _py_black_toolchain = "py_black_toolchain",
)

py_black_toolchain = _py_black_toolchain
