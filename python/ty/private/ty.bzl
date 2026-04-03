"""Bazel rules for ty"""

load("//python:py_info.bzl", "PyInfo")
load("//python/private:target_srcs.bzl", "find_srcs", "target_sources_aspect")
load("//python/venv:defs.bzl", "py_venv_common")
load(":ty_toolchain.bzl", "TOOLCHAIN_TYPE", "rlocationpath")

def _py_ty_test_impl(ctx):
    venv_toolchain = ctx.toolchains[py_venv_common.TOOLCHAIN_TYPE]

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner, ctx.attr.target],
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._runner_main],
        dep_info = dep_info,
    )

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._runner_main,
        runfiles = dep_info.runfiles,
    )

    srcs = find_srcs(ctx.attr.target)

    args = ctx.actions.args()
    args.set_param_file_format("multiline")
    args.add("--config", rlocationpath(ctx.file.config, ctx.workspace_name))
    for src in srcs.to_list():
        args.add("--src", rlocationpath(src, ctx.workspace_name))

    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]
    if toolchain.ty_bin:
        args.add("--ty", rlocationpath(toolchain.ty_bin))

    args_file = ctx.actions.declare_file("{}.ty_args.txt".format(ctx.label.name))
    ctx.actions.write(
        output = args_file,
        content = args,
    )

    return [
        DefaultInfo(
            files = depset([executable]),
            runfiles = runfiles.merge(
                ctx.runfiles(files = [ctx.file.config, args_file], transitive_files = toolchain.all_files),
            ),
            executable = executable,
        ),
        RunEnvironmentInfo(
            environment = {
                "RULES_VENV_TY_RUNNER_ARGS_FILE": rlocationpath(args_file, ctx.workspace_name),
            },
        ),
    ]

py_ty_test = rule(
    implementation = _py_ty_test_impl,
    doc = "A rule for running `ty check` on a Python target.",
    attrs = {
        "config": attr.label(
            doc = "The config file (`ty.toml`) containing ty settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/ty:config"),
        ),
        "target": attr.label(
            doc = "The target to run `ty` on.",
            providers = [PyInfo],
            mandatory = True,
            aspects = [target_sources_aspect],
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running ty.",
            cfg = "exec",
            default = Label("//python/ty/private:ty_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the ty runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/ty/private:ty_runner.py"),
        ),
    },
    toolchains = [
        TOOLCHAIN_TYPE,
        py_venv_common.TOOLCHAIN_TYPE,
    ],
    test = True,
)

_IGNORE_TAGS = [
    "no_ty",
    "noty",
    "no_lint",
    "nolint",
]

def _py_ty_aspect_impl(target, ctx):
    for tag in ctx.rule.attr.tags:
        sanitized = tag.replace("-", "_").lower()
        if sanitized in _IGNORE_TAGS:
            return []

    srcs = find_srcs(target, ctx)
    if not srcs:
        return []

    venv_toolchain = py_venv_common.get_toolchain(ctx, cfg = "exec")

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner, target],
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._runner_main],
        dep_info = dep_info,
    )

    marker = ctx.actions.declare_file("{}.ty.ok".format(target.label.name))
    aspect_name = "{}.ty".format(target.label.name)

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._runner_main,
        name = aspect_name,
        runfiles = dep_info.runfiles,
        use_runfiles_in_entrypoint = False,
        force_runfiles = True,
    )

    args = ctx.actions.args()
    args.add("--config", ctx.file._config)
    args.add("--marker", marker)
    args.add_all(srcs, format_each = "--src=%s")

    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]
    if toolchain.ty_bin:
        args.add("--ty", toolchain.ty_bin)

    ctx.actions.run(
        mnemonic = "PyTy",
        progress_message = "PyTy %{label}",
        executable = executable,
        inputs = depset([ctx.file._config], transitive = [srcs]),
        tools = depset(transitive = [runfiles.files, toolchain.all_files]),
        outputs = [marker],
        arguments = [args],
        env = ctx.configuration.default_shell_env,
    )

    return [OutputGroupInfo(
        py_ty_checks = depset([marker]),
    )]

py_ty_aspect = aspect(
    implementation = _py_ty_aspect_impl,
    doc = """\
An aspect for running ty on targets with Python sources.

This aspect can be configured by adding the following snippet to a workspace's `.bazelrc` file:

```text
build --aspects=@rules_venv//python/ty:py_ty_aspect.bzl%py_ty_aspect
build --output_groups=+py_ty_checks
```
""",
    attrs = {
        "_config": attr.label(
            doc = "The config file (`ty.toml`) containing ty settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/ty:config"),
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running ty.",
            cfg = "exec",
            default = Label("//python/ty/private:ty_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the ty runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/ty/private:ty_runner.py"),
        ),
    } | py_venv_common.create_venv_attrs(),
    toolchains = [TOOLCHAIN_TYPE],
    required_providers = [PyInfo],
    requires = [
        target_sources_aspect,
    ],
)
