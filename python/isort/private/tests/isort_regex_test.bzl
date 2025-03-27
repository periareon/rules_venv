"""Rules for asserting import order of python sources"""

load("//python:defs.bzl", "py_test")

def isort_regex_test(*, name, src, expectation, **kwargs):
    """Test that a particular string exists within a given source file.

    This test is useful for ensuring imports are in the correct order.

    Args:
        name (str): The name of the target.
        src (Label): The source file to check.
        expectation (str): A string of the expected import order.
        **kwargs (dict): Additional keyword arguments.
    """
    main = Label("//python/isort/private/tests:isort_regex_test.py")
    py_test(
        name = name,
        srcs = [main],
        main = main,
        env = {
            "ISORT_REGEX_EXPECTATION": json.encode("\n".join(expectation.splitlines())),
            "ISORT_REGEX_SRC": "$(rlocationpath {})".format(src),
        },
        data = [src],
        deps = ["@rules_python//python/runfiles"],
        # TODO: Enable when this issue is resolved
        # https://github.com/bazelbuild/rules_python/issues/2141
        target_compatible_with = select({
            "@platforms//os:windows": ["@platforms//:incompatible"],
            "//conditions:default": [],
        }),
        **kwargs
    )
