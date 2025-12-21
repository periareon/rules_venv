"""# py_pylint_test"""

load(
    "//python/pylint/private:pylint.bzl",
    _py_pylint_test = "py_pylint_test",
)

py_pylint_test = _py_pylint_test
