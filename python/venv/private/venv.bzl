"""Bazel rules for Python venvs"""

load("@rules_python//python:defs.bzl", "PyInfo")
load(":venv_common.bzl", venv_common = "py_venv_common")

PyMainInfo = provider(
    "`rules_venv` internal provider to inform consumers of binaries about their main entrypoint.",
    fields = {
        "main": "(File) The main entrypoint for the target.",
        "srcs": "(list[File]) The list of source files that directly belong to the binary.",
    },
)

_COMMON_ATTRS = {
    "data": attr.label_list(
        doc = "Files needed by this rule at runtime. May list file or rule targets. Generally allows any target.",
        allow_files = True,
    ),
    "deps": attr.label_list(
        doc = "Other python targets to link to the current target.",
        providers = [PyInfo],
    ),
    "imports": attr.string_list(
        doc = "List of import directories to be added to the `PYTHONPATH`.",
    ),
    "srcs": attr.label_list(
        doc = "The list of source (.py) files that are processed to create the target.",
        allow_files = [".py"],
    ),
}

def _py_venv_library_impl(ctx):
    dep_info = venv_common.create_dep_info(
        ctx = ctx,
        deps = ctx.attr.deps,
    )

    runfiles = ctx.runfiles(
        files = ctx.files.srcs + ctx.files.data,
    ).merge_all(
        [
            dep_info.runfiles,
        ] + [
            target[DefaultInfo].default_runfiles
            for target in ctx.attr.data
        ],
    )

    return [
        DefaultInfo(
            files = depset(ctx.files.srcs),
            runfiles = runfiles,
        ),
        venv_common.create_py_info(
            ctx = ctx,
            imports = ctx.attr.imports,
            srcs = ctx.files.srcs,
            dep_info = dep_info,
        ),
        coverage_common.instrumented_files_info(
            ctx,
            dependency_attributes = ["deps"],
            extensions = ["py"],
            source_attributes = ["srcs"],
        ),
    ]

py_venv_library = rule(
    doc = """\
A library of Python code that can be depended upon.
""",
    implementation = _py_venv_library_impl,
    attrs = _COMMON_ATTRS,
    provides = [PyInfo],
    toolchains = [venv_common.TOOLCHAIN_TYPE],
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

def _compute_main(ctx, srcs, main = None):
    """Determine the main entrypoint for executable rules.

    Args:
        ctx (ctx): The rule's context object.
        srcs (list): A list of File objects.
        main (File, optional): An explicit contender for the main entrypoint.

    Returns:
        File: The file to use for the main entrypoint.
    """
    if main:
        if main not in srcs:
            fail("`main` was not found in `srcs`. Please add `{}` to `srcs` for {}".format(
                main.path,
                ctx.label,
            ))
        return main

    if len(srcs) == 1:
        main = srcs[0]
    else:
        for src in srcs:
            if main:
                fail("Multiple files match candidates for `main`. Please explicitly specify which to use for {}".format(
                    ctx.label,
                ))

            basename = src.basename[:-len(".py")]
            if basename == ctx.label.name:
                main = src

    if not main:
        fail("`main` and no `srcs` were specified. Please update {}".format(
            ctx.label,
        ))

    return main

def _py_venv_binary_impl(ctx):
    venv_toolchain = ctx.toolchains[venv_common.TOOLCHAIN_TYPE]

    dep_info = venv_common.create_dep_info(
        ctx = ctx,
        deps = ctx.attr.deps,
    )

    py_info = venv_common.create_py_info(
        ctx = ctx,
        imports = ctx.attr.imports,
        srcs = ctx.files.srcs,
        dep_info = dep_info,
    )

    direct_runfiles = ctx.runfiles(files = ctx.files.srcs + ctx.files.data).merge_all(
        [
            dep_info.runfiles,
        ] + [
            target[DefaultInfo].default_runfiles
            for target in ctx.attr.data
        ],
    )

    executable, runfiles = venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = _compute_main(
            ctx = ctx,
            main = ctx.file.main,
            srcs = ctx.files.srcs,
        ),
        runfiles = direct_runfiles,
    )

    return [
        DefaultInfo(
            files = depset([executable] + ctx.files.srcs + ctx.files.data),
            runfiles = runfiles,
            executable = executable,
        ),
        py_info,
        coverage_common.instrumented_files_info(
            ctx,
            dependency_attributes = ["deps"],
            extensions = ["py"],
            source_attributes = ["srcs"],
        ),
        _create_run_environment_info(
            ctx = ctx,
            env = ctx.attr.env,
            env_inherit = [],
            targets = ctx.attr.data,
        ),
        PyMainInfo(
            main = ctx.file.main,
            srcs = ctx.files.srcs,
        ),
    ]

def _py_venv_zipapp_impl(ctx):
    venv_toolchain = ctx.toolchains[venv_common.TOOLCHAIN_TYPE]
    py_info = ctx.attr.binary[PyInfo]
    main_info = ctx.attr.binary[PyMainInfo]

    python_zip_file = venv_common._create_python_zip_file(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = _compute_main(
            ctx = ctx,
            main = main_info.main,
            srcs = main_info.srcs,
        ),
        runfiles = ctx.attr.binary[DefaultInfo].default_runfiles,
        files_to_run = ctx.attr.binary[DefaultInfo].files_to_run,
    )

    return DefaultInfo(
        files = depset([python_zip_file]),
    )

py_venv_zipapp = rule(
    doc = """\
A `py_venv_zipapp` is an executable Python zipapp which contains all of the
dependencies and runfiles for a given executable.

```python
load("@rules_venv//python/venv:defs.bzl", "py_venv_binary", "py_venv_zipapp")

py_venv_binary(
    name = "foo",
    srcs = ["foo.py"],
)

py_venv_zipapp(
    name = "foo_pyz",
    binary = ":foo",
)
```
""",
    implementation = _py_venv_zipapp_impl,
    attrs = {
        "binary": attr.label(
            doc = "The binary to package as a zipapp.",
            providers = [PyInfo],
            executable = True,
            cfg = "target",
        ),
    },
    toolchains = [venv_common.TOOLCHAIN_TYPE],
)

_EXECUTABLE_ATTRS = _COMMON_ATTRS | {
    "env": attr.string_dict(
        doc = "Dictionary of strings; values are subject to `$(location)` and \"Make variable\" substitution.",
    ),
    "main": attr.label(
        doc = (
            "The name of the source file that is the main entry point of the application. " +
            "This file must also be listed in `srcs`. If left unspecified, `name` is used " +
            "instead. If `name` does not match any filename in `srcs`, `main` must be specified. "
        ),
        allow_single_file = [".py"],
    ),
}

py_venv_binary = rule(
    doc = """\
A `py_venv_binary` is an executable Python program consisting of a collection of
`.py` source files (possibly belonging to other `py_library` rules), a `*.runfiles`
directory tree containing all the code and data needed by the program at run-time,
and a stub script that starts up the program with the correct initial environment
and data.

```python
load("@rules_venv//python/venv:defs.bzl", "py_venv_binary")

py_venv_binary(
    name = "foo",
    srcs = ["foo.py"],
    data = [":transform"],  # a cc_binary which we invoke at run time
    deps = [
        ":bar",  # a py_library
    ],
)
```
""",
    implementation = _py_venv_binary_impl,
    attrs = _EXECUTABLE_ATTRS,
    provides = [PyInfo],
    toolchains = [venv_common.TOOLCHAIN_TYPE],
    executable = True,
)

def _py_venv_test_impl(ctx):
    venv_toolchain = ctx.toolchains[venv_common.TOOLCHAIN_TYPE]
    py_toolchain = venv_toolchain.py_toolchain

    dep_info = venv_common.create_dep_info(
        ctx = ctx,
        deps = ctx.attr.deps,
    )

    py_info = venv_common.create_py_info(
        ctx = ctx,
        imports = ctx.attr.imports,
        srcs = ctx.files.srcs,
        dep_info = dep_info,
    )

    direct_runfiles = ctx.runfiles(files = ctx.files.srcs + ctx.files.data).merge_all(
        [
            dep_info.runfiles,
        ] + [
            target[DefaultInfo].default_runfiles
            for target in ctx.attr.data
        ],
    )

    executable, runfiles = venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = _compute_main(
            ctx = ctx,
            main = ctx.file.main,
            srcs = ctx.files.srcs,
        ),
        runfiles = direct_runfiles,
    )

    coverage_files_direct = []
    coverage_files_transitive = []
    if ctx.configuration.coverage_enabled:
        py_runtime = py_toolchain.py3_runtime
        if py_runtime.coverage_tool:
            coverage_files_direct.append(py_runtime.coverage_tool)
        if py_runtime.coverage_files:
            coverage_files_transitive.append(py_runtime.coverage_files)

    return [
        DefaultInfo(
            files = depset([executable] + ctx.files.srcs + ctx.files.data),
            runfiles = runfiles,
            executable = executable,
        ),
        py_info,
        coverage_common.instrumented_files_info(
            ctx,
            dependency_attributes = ["deps"],
            extensions = ["py"],
            source_attributes = ["srcs"],
        ),
        _create_run_environment_info(
            ctx = ctx,
            env = ctx.attr.env,
            env_inherit = ctx.attr.env_inherit,
            targets = ctx.attr.data,
        ),
    ]

_COVERAGE_ATTRS = {
    "_collect_cc_coverage": attr.label(
        default = "@bazel_tools//tools/test:collect_cc_coverage",
        executable = True,
        cfg = "exec",
    ),
    # Bazel’s coverage runner
    # (https://github.com/bazelbuild/bazel/blob/6.0.0/tools/test/collect_coverage.sh)
    # needs a binary called “lcov_merge.”  Its location is passed in the
    # LCOV_MERGER environmental variable.  For builtin rules, this variable
    # is set automatically based on a magic “$lcov_merger” or
    # “:lcov_merger” attribute, but it’s not possible to create such
    # attributes in Starlark.  Therefore we specify the variable ourselves.
    # Note that the coverage runner runs in the runfiles root instead of
    # the execution root, therefore we use “path” instead of “short_path.”
    "_lcov_merger": attr.label(
        default = configuration_field(fragment = "coverage", name = "output_generator"),
        executable = True,
        cfg = "exec",
    ),
}

py_venv_test = rule(
    doc = """\
A `py_venv_test` rule compiles a test. A test is a binary wrapper around some test code.
""",
    implementation = _py_venv_test_impl,
    attrs = _EXECUTABLE_ATTRS | _COVERAGE_ATTRS | {
        "env_inherit": attr.string_list(
            doc = "Specifies additional environment variables to inherit from the external environment when the test is executed by `bazel test`.",
        ),
    },
    provides = [PyInfo],
    toolchains = [venv_common.TOOLCHAIN_TYPE],
    test = True,
)
