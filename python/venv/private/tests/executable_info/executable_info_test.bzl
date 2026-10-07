"""Unittests verifying `py_binary`, `py_test`, and their `py_venv_*` counterparts return `PyExecutableInfo`."""

load("@bazel_skylib//lib:unittest.bzl", "analysistest", "asserts")
load("//python:py_executable_info.bzl", "PyExecutableInfo")
load("//python/venv:defs.bzl", "py_binary", "py_library", "py_test", "py_venv_binary", "py_venv_test")

def _executable_info_test_impl(ctx):
    env = analysistest.begin(ctx)
    target = analysistest.target_under_test(env)

    asserts.true(env, PyExecutableInfo in target, "Expected {} to provide `PyExecutableInfo`".format(target.label))
    info = target[PyExecutableInfo]

    asserts.equals(env, ctx.file.main, info.main)
    asserts.equals(env, None, info.build_data_file)
    asserts.true(env, bool(info.interpreter_path), "Expected a non-empty `interpreter_path`")

    without_exe = {file.basename: None for file in info.runfiles_without_exe.files.to_list()}
    default = {file.basename: None for file in target[DefaultInfo].default_runfiles.files.to_list()}
    executable = target[DefaultInfo].files_to_run.executable

    # The program's own sources, data, and dependencies are present.
    for basename in [ctx.file.main.basename] + ctx.attr.expected:
        asserts.true(
            env,
            basename in without_exe,
            "Expected `{}` in `runfiles_without_exe` of {}".format(basename, target.label),
        )

    # Everything in `runfiles_without_exe` is in the default runfiles.
    for basename in without_exe:
        asserts.true(
            env,
            basename in default,
            "`{}` is in `runfiles_without_exe` but not the default runfiles of {}".format(basename, target.label),
        )

    # Files which only exist to support the generated entrypoint are absent.
    for basename in [executable.basename, "venv_process_wrapper.py"] + [
        file.basename
        for file in target[DefaultInfo].default_runfiles.files.to_list()
        if file.basename.endswith(".venv_config.json")
    ]:
        asserts.true(env, basename in default, "Expected `{}` in the default runfiles of {}".format(basename, target.label))
        asserts.false(
            env,
            basename in without_exe,
            "Expected `{}` to be excluded from `runfiles_without_exe` of {}".format(basename, target.label),
        )

    return analysistest.end(env)

executable_info_test = analysistest.make(
    _executable_info_test_impl,
    attrs = {
        "expected": attr.string_list(
            doc = "Basenames expected within `runfiles_without_exe`.",
        ),
        "main": attr.label(
            doc = "The file expected to be `PyExecutableInfo.main`.",
            allow_single_file = True,
            mandatory = True,
        ),
    },
)

def executable_info_test_suite(name, **kwargs):
    """Define a test suite for `PyExecutableInfo` on `rules_venv` executables.

    Args:
        name (str): The name of the test suite.
        **kwargs (dict): Additional keyword arguments for the test suite.
    """
    py_library(
        name = "lib",
        srcs = ["lib.py"],
        data = ["data.txt"],
        tags = ["manual"],
    )

    py_binary(
        name = "binary",
        srcs = ["main.py"],
        main = "main.py",
        deps = [":lib"],
        tags = ["manual"],
    )

    py_test(
        name = "test",
        srcs = ["main_test.py"],
        deps = [":lib"],
        tags = ["manual"],
    )

    py_venv_binary(
        name = "venv_binary",
        srcs = ["main.py"],
        main = "main.py",
        deps = [":lib"],
        tags = ["manual"],
    )

    py_venv_test(
        name = "venv_test",
        srcs = ["main_test.py"],
        main = "main_test.py",
        deps = [":lib"],
        tags = ["manual"],
    )

    tests = []
    for target, main in [
        ("binary", "main.py"),
        ("test", "main_test.py"),
        ("venv_binary", "main.py"),
        ("venv_test", "main_test.py"),
    ]:
        test_name = "{}_executable_info_test".format(target)
        executable_info_test(
            name = test_name,
            target_under_test = ":" + target,
            main = main,
            expected = ["lib.py", "data.txt"],
        )
        tests.append(":" + test_name)

    native.test_suite(
        name = name,
        tests = tests,
        **kwargs
    )
