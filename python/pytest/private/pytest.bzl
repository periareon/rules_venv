"""Pytest rules for Bazel"""

load("@bazel_skylib//rules:common_settings.bzl", "BuildSettingInfo")
load("//python:defs.bzl", "PyInfo", "py_library")
load("//python/private:coverage.bzl", "COVERAGE_ATTRS")
load("//python/venv:defs.bzl", "py_venv_common")

_RULES_VENV_PYTEST_TEST_ARGS_FILE = "RULES_VENV_PYTEST_TEST_ARGS_FILE"

test_configs = struct(
    coverage_rc = Label("//python/pytest:coverage_rc"),
    pytest_config = Label("//python/pytest:config"),
)

def _create_run_environment_info(ctx, env, env_inherit, targets):
    """Create an environment info provider

    This macro performs location expansions.

    Args:
        ctx (ctx): The rule's context object.
        env (dict): Environment variables to set.
        env_inherit (list): Environment variables to inehrit from the host.
        targets (List[Target]): Targets to use in location expansion.

    Returns:
        RunEnvironmentInfo: The provider.
    """

    known_variables = {}
    for target in ctx.attr.toolchains:
        if platform_common.TemplateVariableInfo in target:
            variables = getattr(target[platform_common.TemplateVariableInfo], "variables", {})
            known_variables.update(variables)

    expanded_env = {}
    for key, value in env.items():
        expanded_env[key] = ctx.expand_make_variables(
            key,
            ctx.expand_location(value, targets),
            known_variables,
        )

    workspace_name = ctx.label.workspace_name
    if not workspace_name:
        workspace_name = ctx.workspace_name

    # Needed for bzlmod-aware runfiles resolution.
    expanded_env["REPOSITORY_NAME"] = workspace_name

    return RunEnvironmentInfo(
        environment = expanded_env,
        inherited_environment = env_inherit,
    )

def _is_pytest_test(src):
    basename = src.basename

    if basename == "__init__.py":
        return False

    return True

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _py_pytest_test_impl(ctx):
    # Gather args for the runner
    runner_args = ctx.actions.args()
    runner_args.set_param_file_format("multiline")
    runner_args.add("--cov-config={}".format(_rlocationpath(ctx.file.coverage_rc, ctx.workspace_name)))
    runner_args.add("--pytest-config={}".format(_rlocationpath(ctx.file.config, ctx.workspace_name)))

    workspace_name = ctx.workspace_name

    def _src_map(file):
        if not _is_pytest_test(file):
            return None

        return _rlocationpath(file, workspace_name)

    # Add the test sources.
    runner_args.add_all(
        ctx.files.srcs,
        map_each = _src_map,
        format_each = "--src=%s",
        allow_closure = True,
    )

    exec_requirements = {}

    # Optionally enable multi-threading
    if ctx.attr.numprocesses > 0:
        numprocesses = ctx.attr.numprocesses
        runner_args.add("--numprocesses={}".format(numprocesses))
        exec_requirements["resources:cpu:{}".format(numprocesses)] = str(numprocesses)

    # Separate runner args from other inputs
    runner_args.add("--")

    runner_args.add_all(ctx.attr._extra_args[BuildSettingInfo].value)
    for arg in ctx.attr._extra_args[BuildSettingInfo].value:
        if arg.startswith(("--numprocesses=", "-n=")) or arg in ("--numprocesses", "-n"):
            fail("`{}` is not an acceptable extra argument for pytest. Please remove it".format(arg))

    for arg in ctx.attr.args:
        runner_args.add(ctx.expand_location(arg, ctx.attr.data))

    args_file = ctx.actions.declare_file("{}.pytest_args.txt".format(ctx.label.name))
    ctx.actions.write(
        output = args_file,
        content = runner_args,
    )

    cfg = "target"
    if not ctx.attr._incompatible_cfg_target_toolchain[BuildSettingInfo].value:
        cfg = "exec"

    venv_toolchain = py_venv_common.get_toolchain(ctx, cfg = cfg)

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner] + ctx.attr.deps,
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._runner_main] + ctx.files.srcs,
        dep_info = dep_info,
    )

    direct_runfiles = ctx.runfiles(files = [
        args_file,
        ctx.file.config,
        ctx.file.coverage_rc,
    ] + ctx.files.srcs + ctx.files.data).merge_all([
        dep_info.runfiles,
    ] + [
        target[DefaultInfo].default_runfiles
        for target in ctx.attr.data
    ])

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._runner_main,
        runfiles = direct_runfiles,
    )

    return [
        py_info,
        DefaultInfo(
            executable = executable,
            runfiles = runfiles,
        ),
        testing.ExecutionInfo(
            requirements = exec_requirements,
        ),
        _create_run_environment_info(
            ctx,
            env = ctx.attr.env | {
                _RULES_VENV_PYTEST_TEST_ARGS_FILE: _rlocationpath(args_file, ctx.workspace_name),
            },
            env_inherit = ctx.attr.env_inherit,
            targets = ctx.attr.data,
        ),
        coverage_common.instrumented_files_info(
            ctx,
            source_attributes = ["srcs"],
            dependency_attributes = ["deps", "data"],
            extensions = ["py"],
        ),
    ]

py_pytest_test = rule(
    doc = """\
A rule which runs python tests using [pytest][pt] as the [py_test][bpt] test runner.

This rule also supports a build setting for globally applying extra flags to test invocations.
Users can add something similar to the following to their `.bazelrc` files:

```text
build --@rules_venv//python/pytest:extra_args=--color=yes,-vv
```

The example above will add `--colors=yes` and `-vv` arguments to the end of the pytest invocation.

Tips:

- It's common for tests to have some utility code that does not live in a test source file.
To account for this. A `py_library` can be created that contains only these sources which are then
passed to `py_pytest_test` via `deps`.

```python
load("@rules_venv//python:defs.bzl", "py_library")
load("@rules_venv//python/pytest:defs.bzl", "py_pytest_test")

py_library(
    name = "test_utils",
    srcs = [
        "tests/__init__.py",
        "tests/conftest.py",
    ],
    deps = ["@rules_venv//python/pytest:current_py_pytest_toolchain"],
    testonly = True,
)

py_pytest_test(
    name = "test",
    srcs = ["tests/example_test.py"],
    deps = [":test_utils"],
)
```

[pt]: https://docs.pytest.org/en/latest/
[bpt]: https://docs.bazel.build/versions/master/be/python.html#py_test
[ptx]: https://pypi.org/project/pytest-xdist/
""",
    implementation = _py_pytest_test_impl,
    attrs = {
        "config": attr.label(
            doc = "The pytest configuration file to use.",
            allow_single_file = True,
            default = Label("//python/pytest:config"),
        ),
        "coverage_rc": attr.label(
            doc = "The pytest-cov configuration file to use.",
            allow_single_file = True,
            default = Label("//python/pytest:coverage_rc"),
        ),
        "data": attr.label_list(
            doc = "Files needed by this rule at runtime. May list file or rule targets. Generally allows any target.",
            allow_files = True,
        ),
        "deps": attr.label_list(
            doc = "The list of other libraries to be linked in to the binary target.",
            providers = [PyInfo],
        ),
        "env": attr.string_dict(
            doc = "Dictionary of strings; values are subject to `$(location)` and \"Make variable\" substitution",
            default = {},
        ),
        "env_inherit": attr.string_list(
            doc = "Specifies additional environment variables to inherit from the external environment when the test is executed by `bazel test`.",
        ),
        "numprocesses": attr.int(
            doc = (
                "If set the [pytest-xdist](https://pypi.org/project/pytest-xdist/) " +
                "argument `--numprocesses` (`-n`) will be passed to the test. Note that " +
                "the a value 0 or less indicates this flag should not be passed."
            ),
            default = 0,
        ),
        "srcs": attr.label_list(
            doc = "An explicit list of source files to test.",
            allow_files = [".py"],
        ),
        "_extra_args": attr.label(
            doc = "Additional global args to pass to pytest.",
            default = Label("//python/pytest:extra_args"),
        ),
        "_incompatible_cfg_target_toolchain": attr.label(
            default = Label("//python/pytest/settings:incompatible_cfg_target_toolchain"),
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running pytest.",
            cfg = "target",
            default = Label("//python/pytest/private:pytest_process_wrapper"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the pytest process.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/pytest/private:pytest_process_wrapper.py"),
        ),
    } | COVERAGE_ATTRS | py_venv_common.create_venv_attrs(),
    toolchains = [py_venv_common.TOOLCHAIN_TYPE],
    test = True,
    provides = [
        PyInfo,
    ],
)

def _py_pytest_toolchain_impl(ctx):
    pytest_target = ctx.attr.pytest

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = pytest_target[DefaultInfo].files,
        runfiles = pytest_target[DefaultInfo].default_runfiles,
    )

    return [
        platform_common.ToolchainInfo(
            pytest = ctx.attr.pytest,
        ),
        default_info,
        pytest_target[PyInfo],
        pytest_target[OutputGroupInfo],
        pytest_target[InstrumentedFilesInfo],
    ]

py_pytest_toolchain = rule(
    implementation = _py_pytest_toolchain_impl,
    doc = "A toolchain for the [pytest](https://python/pytest.readthedocs.io/en/stable/) rules.",
    attrs = {
        "pytest": attr.label(
            doc = "The pytest `py_library` to use with the rules.",
            providers = [PyInfo],
            mandatory = True,
        ),
    },
)

def _current_py_pytest_toolchain_impl(ctx):
    toolchain = ctx.toolchains[str(Label("//python/pytest:toolchain_type"))]

    pytest_target = toolchain.pytest

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = pytest_target[DefaultInfo].files,
        runfiles = pytest_target[DefaultInfo].default_runfiles,
    )

    return [
        toolchain,
        default_info,
        pytest_target[PyInfo],
        pytest_target[OutputGroupInfo],
        pytest_target[InstrumentedFilesInfo],
    ]

current_py_pytest_toolchain = rule(
    doc = "A rule for exposing the current registered `py_pytest_toolchain`.",
    implementation = _current_py_pytest_toolchain_impl,
    toolchains = [
        str(Label("//python/pytest:toolchain_type")),
    ],
)

def py_pytest_test_suite(
        name,
        tests,
        args = [],
        data = [],
        **kwargs):
    """Generates a [test_suite][ts] which groups various test targets for a set of python sources.

    Given an idiomatic python project structure:
    ```text
    BUILD.bazel
    my_lib/
        __init__.py
        mod_a.py
        mod_b.py
        mod_c.py
    requirements.in
    requirements.txt
    tests/
        __init__.py
        fixtures.py
        test_mod_a.py
        test_mod_b.py
        test_mod_c.py
    ```

    This rule can be used to easily define test targets:

    ```python
    load("@rules_venv//python:defs.bzl", "py_library")
    load("@rules_venv//python/pytest:defs.bzl", "py_pytest_test_suite")

    py_library(
        name = "my_lib",
        srcs = glob(["my_lib/**/*.py"])
        imports = ["."],
    )

    py_pytest_test_suite(
        name = "my_lib_test_suite",
        # Source files containing test helpers should go here.
        # Note that the test sources are excluded. This avoids
        # a test to be updated without invalidating all other
        # targets.
        srcs = glob(
            include = ["tests/**/*.py"],
            exclude = ["tests/**/*_test.py"],
        ),
        # Any data files the tests may need would be passed here
        data = glob(["tests/**/*.json"]),
        # This field is used for dedicated test files.
        tests = glob(["tests/**/*_test.py"]),
        deps = [
            ":my_lib",
        ],
    )
    ```

    For each file passed to `tests`, a [py_pytest_test](#py_pytest_test) target will be created. From the example above,
    the user should expect to see the following test targets:
    ```text
    //:my_lib_test_suite
    //:tests/test_mod_a
    //:tests/test_mod_b
    //:tests/test_mod_c
    ```

    Additional Notes:
    - No file passed to `tests` should be passed found in the `srcs` or `data` attributes or tests will not be able
        to be individually cached.

    [pt]: https://docs.bazel.build/versions/master/be/python.html#py_test
    [ts]: https://docs.bazel.build/versions/master/be/general.html#test_suite

    Args:
        name (str): The name of the test suite
        tests (list): A list of source files, typically `glob(["tests/**/*_test.py"])`, which are converted
            into test targets.
        args (list, optional): Arguments for the underlying `py_pytest_test` targets.
        data (list, optional): A list of additional data for the test. This field would also include python
            files containing test helper functionality.
        **kwargs: Keyword arguments passed to the underlying `py_test` rule.
    """

    tests_targets = []

    common_kwargs = {
        "target_compatible_with": kwargs.get("target_compatible_with"),
        "visibility": kwargs.get("visibility"),
    }

    tags = kwargs.get("tags", [])
    deps = kwargs.pop("deps", [])
    srcs = kwargs.pop("srcs", [])
    if srcs:
        test_lib_name = name + "_test_lib"
        py_library(
            name = test_lib_name,
            srcs = srcs,
            deps = deps,
            data = data,
            testonly = True,
            tags = depset(tags + ["manual"]).to_list(),
            **common_kwargs
        )
        deps = [test_lib_name] + deps

    for src in tests:
        src_name = src.name if type(src) == "Label" else src
        if not src_name.endswith(".py"):
            fail("srcs should have `.py` extensions")

        # The test name should not end with `.py`
        test_name = src_name[:-3]
        py_pytest_test(
            name = test_name,
            args = args,
            srcs = [src],
            data = data,
            deps = deps,
            **kwargs
        )

        tests_targets.append(test_name)

    native.test_suite(
        name = name,
        tests = tests_targets,
        tags = tags,
        **common_kwargs
    )
