"""Bazel rules for isort"""

load("//python:py_info.bzl", "PyInfo")
load("//python/private:target_srcs.bzl", "PySourcesInfo", "target_sources_aspect")
load("//python/venv:defs.bzl", "py_venv_common")

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _py_isort_test_impl(ctx):
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

    srcs_info = ctx.attr.target[PySourcesInfo]

    args_file = ctx.actions.declare_file("{}.isort_args.txt".format(ctx.label.name))
    ctx.actions.write(
        output = args_file,
        content = "\n".join([
            "--settings-path",
            _rlocationpath(ctx.file.config, ctx.workspace_name),
        ] + [
            "--import={}".format(path)
            for path in srcs_info.imports.to_list()
        ] + [
            "--src={}".format(_rlocationpath(src, ctx.workspace_name))
            for src in srcs_info.srcs.to_list()
        ] + [
            "--",
            "--check-only",
            "--diff",
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
                "RULES_VENV_ISORT_RUNNER_ARGS_FILE": _rlocationpath(args_file, ctx.workspace_name),
            },
        ),
    ]

py_isort_test = rule(
    implementation = _py_isort_test_impl,
    doc = "A rule for running isort on a Python target.",
    attrs = {
        "config": attr.label(
            doc = "The config file (isort.cfg) containing isort settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/isort:config"),
        ),
        "target": attr.label(
            doc = "The target to run `isort` on.",
            providers = [PyInfo],
            mandatory = True,
            aspects = [target_sources_aspect],
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running isort.",
            cfg = "exec",
            default = Label("//python/isort/private:isort_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the isort runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/isort/private:isort_runner.py"),
        ),
    },
    toolchains = [py_venv_common.TOOLCHAIN_TYPE],
    test = True,
)

def _py_isort_aspect_impl(target, ctx):
    ignore_tags = [
        "no_format",
        "no_isort_fmt",
        "no_isort_format",
        "no_isort",
        "noformat",
        "noisort",
    ]
    for tag in ctx.rule.attr.tags:
        sanitized = tag.replace("-", "_").lower()
        if sanitized in ignore_tags:
            return []

    srcs_info = target[PySourcesInfo]
    srcs = srcs_info.srcs.to_list()
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

    marker = ctx.actions.declare_file("{}.isort.ok".format(target.label.name))
    aspect_name = "{}.isort".format(target.label.name)

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
    args.add("--settings-path", ctx.file._config)
    args.add("--marker", marker)
    args.add_all(srcs_info.imports, format_each = "--import=%s")
    args.add_all(srcs, format_each = "--src=%s")
    args.add("--")
    args.add("--check-only")
    args.add("--diff")

    ctx.actions.run(
        mnemonic = "PyIsort",
        progress_message = "PyIsort %{label}",
        executable = executable,
        inputs = depset([ctx.file._config] + srcs),
        tools = runfiles.files,
        outputs = [marker],
        arguments = [args],
        env = ctx.configuration.default_shell_env,
    )

    return [OutputGroupInfo(
        py_isort_checks = depset([marker]),
    )]

py_isort_aspect = aspect(
    implementation = _py_isort_aspect_impl,
    doc = "An aspect for running isort on targets with Python sources.",
    attrs = {
        "_config": attr.label(
            doc = "The config file (isortrc) containing isort settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/isort:config"),
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running isort.",
            cfg = "exec",
            default = Label("//python/isort/private:isort_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the isort runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/isort/private:isort_runner.py"),
        ),
    } | py_venv_common.create_venv_attrs(),
    required_providers = [PyInfo],
    requires = [target_sources_aspect],
)
