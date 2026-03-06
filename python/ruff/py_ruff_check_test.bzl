"""# py_ruff_check_test"""

load(
    "//python/ruff/private:ruff.bzl",
    _py_ruff_check_test = "py_ruff_check_test",
)

py_ruff_check_test = _py_ruff_check_test
