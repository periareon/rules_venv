"""# py_mypy_test"""

load(
    "//python/mypy/private:mypy.bzl",
    _py_mypy_test = "py_mypy_test",
)

py_mypy_test = _py_mypy_test
