"""# py_ruff_test"""

load(":py_ruff_check_test.bzl", "py_ruff_check_test")
load(":py_ruff_format_test.bzl", "py_ruff_format_test")

def py_ruff_test(*, name, target, config = None, **kwargs):
    """A rule for running `ruff check` and `ruff format` on a given target.

    This macro defines the following target:
    | rule | name |
    | --- | --- |
    | (py_ruff_check_test)[#py_ruff_check_test] | `{name}.check` |
    | (py_ruff_format_test)[#py_ruff_format_test] | `{name}.format` |

    Args:
        name (str): The name of the test suite
        target (Label): The target to run `ruff` on.
        config (Label): The config file (ruff.toml) containing ruff settings.
        **kwargs (dict): Additional keyword arguments.
    """
    py_ruff_check_test(
        name = name + ".check",
        target = target,
        config = config,
        **kwargs
    )

    py_ruff_format_test(
        name = name + ".format",
        target = target,
        config = config,
        **kwargs
    )

    native.test_suite(
        name = name,
        tests = [
            name + ".format",
            name + ".check",
        ],
        **kwargs
    )
