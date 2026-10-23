"""Tests of how a wheel names the distributions its external dependencies stand for."""

load("@bazel_skylib//lib:unittest.bzl", "analysistest", "asserts")
load("//python/wheel:defs.bzl", "py_wheel_library")

def _requires_action(env):
    """The action writing the requirements of the wheel under test."""
    for action in analysistest.target_actions(env):
        if action.mnemonic == "PyWheelRequire":
            return action
    asserts.true(env, False, "Expected a `PyWheelRequire` action")
    return None

def _assert_requirement(env, name):
    action = _requires_action(env)
    if action:
        asserts.true(
            env,
            "--dep={}".format(name) in action.argv,
            "Expected `{}` among the requirements, the action was given {}".format(name, action.argv),
        )

def _requirement_from_tag_test_impl(ctx):
    env = analysistest.begin(ctx)
    _assert_requirement(env, "Fancy-Pkg")
    return analysistest.end(env)

# A tagged dependency is named by its tag.
requirement_from_tag_test = analysistest.make(
    _requirement_from_tag_test_impl,
)

def _requirement_from_dist_info_test_impl(ctx):
    env = analysistest.begin(ctx)
    _assert_requirement(env, "Dist_Info_Pkg")
    return analysistest.end(env)

# An untagged dependency is named by its `.dist-info` directory.
requirement_from_dist_info_test = analysistest.make(
    _requirement_from_dist_info_test_impl,
)

def _requirement_from_label_test_impl(ctx):
    env = analysistest.begin(ctx)
    _assert_requirement(env, "plain")
    return analysistest.end(env)

# A dependency with neither is named by its label, less the hub prefix.
requirement_from_label_test = analysistest.make(
    _requirement_from_label_test_impl,
)

def tagged_deps_test_suite(name):
    """Define the test suite.

    Args:
        name (str): The name of the suite.
    """
    py_wheel_library(
        name = "only_fancy",
        deps = ["@wheel_tagged_example//:pip_deps.fancy_pkg"],
    )

    py_wheel_library(
        name = "only_dist_info",
        deps = ["@wheel_tagged_example//:pip_deps.dist_info_pkg"],
    )

    py_wheel_library(
        name = "only_plain",
        deps = ["@wheel_tagged_example//:pip_deps.plain"],
    )

    requirement_from_tag_test(
        name = "requirement_from_tag_test",
        target_under_test = ":only_fancy.package",
    )

    requirement_from_dist_info_test(
        name = "requirement_from_dist_info_test",
        target_under_test = ":only_dist_info.package",
    )

    requirement_from_label_test(
        name = "requirement_from_label_test",
        target_under_test = ":only_plain.package",
    )

    native.test_suite(
        name = name,
        tests = [
            ":requirement_from_dist_info_test",
            ":requirement_from_label_test",
            ":requirement_from_tag_test",
        ],
    )
