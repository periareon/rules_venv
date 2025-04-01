"""Venv utilities"""

def _venv_entrypoint_impl(ctx):
    py_toolchain = ctx.attr._py_toolchain_exec[platform_common.ToolchainInfo]
    py_runtime = py_toolchain.py3_runtime
    interpreter = None
    if py_runtime.interpreter:
        interpreter = py_runtime.interpreter

    if not interpreter:
        fail("Unable to locate interpreter from py_toolchain: {}".format(py_toolchain))

    inputs = [ctx.file.entrypoint]

    substitutions = {}
    file_substitutions = {}

    is_windows = ctx.file.entrypoint.basename.endswith(".bat")
    if is_windows:
        output = ctx.actions.declare_file("{}.bat".format(ctx.label.name))
    else:
        output = ctx.actions.declare_file("{}.sh".format(ctx.label.name))
        sh_toolchain = ctx.toolchains["@bazel_tools//tools/sh:toolchain_type"]
        if sh_toolchain:
            shebang = "#!{}".format(sh_toolchain.path)
            substitutions["#!/usr/bin/env bash"] = shebang

        file_substitutions["# {RUNFILES_API}"] = ctx.file._bash_runfiles.path
        inputs.append(ctx.file._bash_runfiles)

    args = ctx.actions.args()
    args = args.add("-B")  # don't write .pyc files on import; also PYTHONDONTWRITEBYTECODE=x
    args = args.add("-s")  # don't add user site directory to sys.path; also PYTHONNOUSERSITE

    if hasattr(py_runtime, "interpreter_version_info"):
        version_info = py_runtime.interpreter_version_info
        if (version_info.major >= 3 and version_info.minor >= 11) or version_info.major > 3:
            args.add("-P")  # safe paths (available in Python 3.11)

    args.add(ctx.file._maker)
    args.add("--output", output)
    args.add("--template", ctx.file.entrypoint)
    args.add("--substitutions", json.encode(substitutions))
    args.add("--file_substitutions", json.encode(file_substitutions))

    ctx.actions.run(
        mnemonic = "PyVenvEntrypointTemplate",
        executable = interpreter,
        arguments = [args],
        inputs = inputs,
        tools = depset([ctx.file._maker], transitive = [py_runtime.files]),
        outputs = [output],
    )

    return [DefaultInfo(
        files = depset([output]),
        executable = output,
    )]

venv_entrypoint = rule(
    doc = "Generates the entrypoint for `py_venv_*` executable rules.",
    implementation = _venv_entrypoint_impl,
    attrs = {
        "entrypoint": attr.label(
            doc = "The entrypoint template.",
            cfg = "target",
            executable = True,
            allow_single_file = [".sh", ".bat"],
        ),
        "_bash_runfiles": attr.label(
            doc = "The runfiles library for bash.",
            cfg = "target",
            allow_single_file = True,
            default = Label("@bazel_tools//tools/bash/runfiles"),
        ),
        "_maker": attr.label(
            doc = "The script used to render the entrypoint.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/venv/private:venv_entrypoint_maker.py"),
        ),
        "_py_toolchain_exec": attr.label(
            cfg = "exec",
            default = Label("@rules_python//python:current_py_toolchain"),
            providers = [platform_common.ToolchainInfo],
        ),
    },
    toolchains = [
        config_common.toolchain_type("@bazel_tools//tools/sh:toolchain_type", mandatory = False),
    ],
    executable = True,
)
