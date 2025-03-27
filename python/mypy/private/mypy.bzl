"""Bazel rules for mypy"""

load("//python:py_info.bzl", "PyInfo")
load("//python/private:target_srcs.bzl", "find_srcs", "target_sources_aspect")
load("//python/venv:defs.bzl", "py_venv_common")

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _py_mypy_test_impl(ctx):
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

    args_file = ctx.actions.declare_file("{}.mypy_args.txt".format(ctx.label.name))
    ctx.actions.write(
        output = args_file,
        content = "\n".join([
            "--config-file",
            _rlocationpath(ctx.file.config, ctx.workspace_name),
            "--workspace_name",
            ctx.workspace_name,
        ] + [
            "--file={}".format(_rlocationpath(src, ctx.workspace_name))
            for src in srcs.to_list()
        ]),
    )

    return [
        DefaultInfo(
            files = depset([executable]),
            runfiles = runfiles.merge(
                ctx.runfiles(files = [ctx.file.config, args_file]),
            ),
            executable = executable,
        ),
        RunEnvironmentInfo(
            environment = {
                "PY_MYPY_RUNNER_ARGS_FILE": _rlocationpath(args_file, ctx.workspace_name),
            },
        ),
    ]

py_mypy_test = rule(
    implementation = _py_mypy_test_impl,
    doc = "A rule for running mypy on a Python target.",
    attrs = {
        "config": attr.label(
            doc = "The config file (`mypy.ini`) containing mypy settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/mypy:config"),
        ),
        "target": attr.label(
            doc = "The target to run `mypy` on.",
            providers = [PyInfo],
            mandatory = True,
            aspects = [target_sources_aspect],
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running mypy.",
            cfg = "exec",
            default = Label("//python/mypy/private:mypy_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the mypy runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/mypy/private:mypy_runner.py"),
        ),
    },
    toolchains = [py_venv_common.TOOLCHAIN_TYPE],
    test = True,
)

def _py_mypy_aspect_impl(target, ctx):
    ignore_tags = [
        "no_mypy",
        "no_lint",
        "nolint",
        "nomypy",
    ]
    for tag in ctx.rule.attr.tags:
        sanitized = tag.replace("-", "_").lower()
        if sanitized in ignore_tags:
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

    marker = ctx.actions.declare_file("{}.mypy.ok".format(target.label.name))
    aspect_name = "{}.mypy".format(target.label.name)

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
    args.add("--config-file", ctx.file._config)
    args.add("--marker", marker)
    args.add("--workspace_name", ctx.workspace_name)
    args.add_all(srcs, format_each = "--file=%s")

    ctx.actions.run(
        mnemonic = "PyMypy",
        progress_message = "PyMypy %{label}",
        executable = executable,
        inputs = depset([ctx.file._config], transitive = [srcs]),
        tools = runfiles.files,
        outputs = [marker],
        arguments = [args],
        env = ctx.configuration.default_shell_env,
    )

    return [OutputGroupInfo(
        py_mypy_checks = depset([marker]),
    )]

py_mypy_aspect = aspect(
    implementation = _py_mypy_aspect_impl,
    doc = "An aspect for running mypy on targets with Python sources.",
    attrs = {
        "_config": attr.label(
            doc = "The config file (`mypy.ini`) containing mypy settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/mypy:config"),
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running mypy.",
            cfg = "exec",
            default = Label("//python/mypy/private:mypy_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the mypy runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/mypy/private:mypy_runner.py"),
        ),
    } | py_venv_common.create_venv_attrs(),
    required_providers = [PyInfo],
    requires = [target_sources_aspect],
)
