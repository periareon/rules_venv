# py_pytest_test with unique values for `args`

This test shows that targets which pass values to `py_pytest_test.args` work
as expected. In the example here, if `--dist loadgroup` is not passed then the
test is expected to fail. The argument passed is explicitly a
[pytest-xdist](https://pypi.org/project/pytest-xdist/) argument to confirm arguments for
this plugin also work.
