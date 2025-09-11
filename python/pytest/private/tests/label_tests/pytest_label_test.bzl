"""Tests to confirm pytest rules work with labels as sources and tests"""

load("//python/pytest:defs.bzl", "py_pytest_test", "py_pytest_test_suite")

def pytest_label_test(name):
    py_pytest_test(
        name = name + ".non_suite",
        srcs = [Label("//python/pytest/private/tests/label_tests:pytest_label_test.py")],
    )

    py_pytest_test_suite(
        name = name + ".suite",
        tests = [Label("//python/pytest/private/tests/label_tests:pytest_label_test.py")],
    )

    native.test_suite(
        name = name,
        tests = [
            name + ".non_suite",
            name + ".suite",
        ],
    )
