"""# py_test"""

load(
    "//python/venv/private:venv.bzl",
    _py_test = "py_test",
)

py_test = _py_test
