"""# py_isort_test"""

load(
    "//python/isort/private:isort.bzl",
    _py_isort_test = "py_isort_test",
)

py_isort_test = _py_isort_test
