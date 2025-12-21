"""# py_pytest_test_suite"""

load(
    "//python/pytest/private:pytest.bzl",
    _py_pytest_test_suite = "py_pytest_test_suite",
)

py_pytest_test_suite = _py_pytest_test_suite
