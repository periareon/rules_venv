"""Test rules for the `py_venv_common` API."""

load("//python:py_info.bzl", "PyInfo")
load("//python/venv:defs.bzl", "py_venv_common")

def _venv_action_aspect_impl(target, ctx):
    out = ctx.actions.declare_file("{}.venv_test_aspect.txt".format(target.label.name))

    venv_toolchain = py_venv_common.get_toolchain(ctx, cfg = "exec")

    runner = ctx.attr._action_runner

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [runner, target],
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._action_runner_main],
        dep_info = dep_info,
    )

    aspect_name = "{}_aspect".format(target.label.name)

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._action_runner_main,
        name = aspect_name,
        runfiles = dep_info.runfiles,
        use_runfiles_in_entrypoint = False,
        force_runfiles = True,
    )

    args = ctx.actions.args()
    args.add("--output", out)

    ctx.actions.run(
        mnemonic = "VenvTestAction",
        executable = executable,
        tools = runfiles.files,
        outputs = [out],
        arguments = [args],
    )

    return [OutputGroupInfo(
        venv_test_action_output = depset([out]),
    )]

venv_action_aspect = aspect(
    doc = "An aspect for testing `py_venv_common` executables in an action.",
    implementation = _venv_action_aspect_impl,
    attrs = {
        "_action_runner": attr.label(
            cfg = "exec",
            executable = True,
            default = Label("//python/venv/private/tests/common_api/aspect:aspect_tester"),
        ),
        "_action_runner_main": attr.label(
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/venv/private/tests/common_api/aspect:aspect_tester.py"),
        ),
    } | py_venv_common.create_venv_attrs(),
)

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _aspect_user_impl(ctx):
    target = ctx.attr.target
    aspect_output = target[OutputGroupInfo].venv_test_action_output.to_list()[0]

    venv_toolchain = ctx.toolchains[py_venv_common.TOOLCHAIN_TYPE]

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runfiles],
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file.test],
        dep_info = dep_info,
    )

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file.test,
        runfiles = dep_info.runfiles,
    )

    return [
        DefaultInfo(
            files = depset([executable]),
            runfiles = runfiles.merge(ctx.runfiles(files = [aspect_output])),
            executable = executable,
        ),
        RunEnvironmentInfo(
            environment = {
                "ASPECT_ACTION_OUTPUT": _rlocationpath(aspect_output, ctx.workspace_name),
            },
        ),
    ]

aspect_user_test = rule(
    doc = "A test rule which consumes `venv_action_aspect` outputs.",
    implementation = _aspect_user_impl,
    attrs = {
        "target": attr.label(
            doc = "A target to run `venv_action_aspect` on.",
            mandatory = True,
            providers = [PyInfo],
            aspects = [venv_action_aspect],
        ),
        "test": attr.label(
            doc = "The source file to buidl a test for.",
            allow_single_file = True,
            mandatory = True,
        ),
        "_runfiles": attr.label(
            default = Label("//python/runfiles"),
        ),
    },
    toolchains = [py_venv_common.TOOLCHAIN_TYPE],
    test = True,
)
