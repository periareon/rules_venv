"""# py_isort_toolchain"""

load(
    "//python/isort/private:isort_toolchain.bzl",
    _py_isort_toolchain = "py_isort_toolchain",
)

py_isort_toolchain = _py_isort_toolchain
