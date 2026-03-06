"""Bazel rules for ruff"""

load("@bazel_skylib//rules:common_settings.bzl", "BuildSettingInfo")
load("//python:py_info.bzl", "PyInfo")
load("//python/private:target_srcs.bzl", "find_srcs", "target_sources_aspect")
load("//python/venv:defs.bzl", "py_venv_common")
load(":ruff_toolchain.bzl", "TOOLCHAIN_TYPE", "rlocationpath")

def _py_ruff_test_impl_common(ctx, mode):
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
    args.add("--mode", mode)
    args.add("--config", rlocationpath(ctx.file.config, ctx.workspace_name))
    for src in srcs.to_list():
        args.add("--src", rlocationpath(src, ctx.workspace_name))

    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]
    if toolchain.ruff_bin:
        args.add("--ruff", rlocationpath(toolchain.ruff_bin))

    args_file = ctx.actions.declare_file("{}.ruff_args.txt".format(ctx.label.name))
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
                "RULES_VENV_RUFF_RUNNER_ARGS_FILE": rlocationpath(args_file, ctx.workspace_name),
            },
        ),
    ]

_TEST_ATTRS = {
    "config": attr.label(
        doc = "The config file (ruff.toml) containing ruff settings.",
        cfg = "target",
        allow_single_file = True,
        default = Label("//python/ruff:config"),
    ),
    "target": attr.label(
        doc = "The target to run `ruff` on.",
        providers = [PyInfo],
        mandatory = True,
        aspects = [target_sources_aspect],
    ),
    "_runner": attr.label(
        doc = "The process wrapper for running ruff.",
        cfg = "exec",
        default = Label("//python/ruff/private:ruff_runner"),
    ),
    "_runner_main": attr.label(
        doc = "The main entrypoint for the ruff runner.",
        cfg = "exec",
        allow_single_file = True,
        default = Label("//python/ruff/private:ruff_runner.py"),
    ),
}

def _py_ruff_check_test_impl(ctx):
    return _py_ruff_test_impl_common(ctx, "check")

py_ruff_check_test = rule(
    implementation = _py_ruff_check_test_impl,
    doc = "A rule for running `ruff check` on a Python target.",
    attrs = _TEST_ATTRS,
    toolchains = [
        TOOLCHAIN_TYPE,
        py_venv_common.TOOLCHAIN_TYPE,
    ],
    test = True,
)

def _py_ruff_format_test_impl(ctx):
    return _py_ruff_test_impl_common(ctx, "format")

py_ruff_format_test = rule(
    implementation = _py_ruff_format_test_impl,
    doc = "A rule for running `ruff format` on a Python target.",
    attrs = _TEST_ATTRS,
    toolchains = [
        TOOLCHAIN_TYPE,
        py_venv_common.TOOLCHAIN_TYPE,
    ],
    test = True,
)

_IGNORE_TAGS = [
    "no_ruff",
    "noruff",
]

_MODE_IGNORE_TAGS = {
    "check": [
        "no_lint",
        "nolint",
        "no_ruff_lint",
        "no_ruff_check",
    ],
    "format": [
        "no_fmt",
        "no_format",
        "nofmt",
        "noformat",
        "no_ruff_format",
        "no_ruff_fmt",
    ],
}

def _py_ruff_aspect_impl(target, ctx):
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

    aspect_name = "{}.ruff".format(target.label.name)

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
    args.add_all(srcs, format_each = "--src=%s")

    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]
    if toolchain.ruff_bin:
        args.add("--ruff", toolchain.ruff_bin)

    markers = []

    modes = ctx.attr._modes[BuildSettingInfo].value
    for mode in modes:
        # Handle granular tag skipping per mode.
        ignore_tags = _MODE_IGNORE_TAGS[mode]
        skip = False
        for tag in ctx.rule.attr.tags:
            sanitized = tag.replace("-", "_").lower()
            if sanitized in ignore_tags:
                skip = True
                break

        if skip:
            continue

        marker = ctx.actions.declare_file("{}.ruff.{}.ok".format(target.label.name, mode))
        markers.append(marker)

        mode_args = ctx.actions.args()
        mode_args.add("--mode", mode)
        mode_args.add("--marker", marker)

        ctx.actions.run(
            mnemonic = "PyRuff{}".format(mode.capitalize()),
            progress_message = "PyRuff ({}) %{{label}}".format(mode.capitalize()),
            executable = executable,
            inputs = depset([ctx.file._config], transitive = [srcs]),
            tools = depset(transitive = [runfiles.files, toolchain.all_files]),
            outputs = [marker],
            arguments = [mode_args, args],
            env = ctx.configuration.default_shell_env,
        )

    if not markers:
        return []

    return [OutputGroupInfo(
        py_ruff_checks = depset(markers),
    )]

py_ruff_aspect = aspect(
    implementation = _py_ruff_aspect_impl,
    doc = """\
An aspect for running ruff on targets with Python sources.

This aspect can be configured by adding the following snippet to a workspace's `.bazelrc` file:

```text
build --aspects=@rules_venv//python/ruff:py_ruff_aspect.bzl%py_ruff_aspect
build --output_groups=+py_ruff_checks
```
""",
    attrs = {
        "_config": attr.label(
            doc = "The config file (ruff.toml) containing ruff settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/ruff:config"),
        ),
        "_modes": attr.label(
            doc = "The type of check ruff should perform.",
            default = Label("//python/ruff:mode"),
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running ruff.",
            cfg = "exec",
            default = Label("//python/ruff/private:ruff_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the ruff runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/ruff/private:ruff_runner.py"),
        ),
    } | py_venv_common.create_venv_attrs(),
    toolchains = [TOOLCHAIN_TYPE],
    required_providers = [PyInfo],
    requires = [
        target_sources_aspect,
    ],
)
