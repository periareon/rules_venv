"""# py_ruff_format_test"""

load(
    "//python/ruff/private:ruff.bzl",
    _py_ruff_format_test = "py_ruff_format_test",
)

py_ruff_format_test = _py_ruff_format_test
