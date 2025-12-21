"""# py_black_test"""

load(
    "//python/black/private:black.bzl",
    _py_black_test = "py_black_test",
)

py_black_test = _py_black_test
