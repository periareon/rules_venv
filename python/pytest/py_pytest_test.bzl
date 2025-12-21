"""# py_pytest_test"""

load(
    "//python/pytest/private:pytest.bzl",
    _py_pytest_test = "py_pytest_test",
)

py_pytest_test = _py_pytest_test
