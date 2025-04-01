"""Pylint toolchain rules."""

load("//python:defs.bzl", "PyInfo")

TOOLCHAIN_TYPE = str(Label("//python/pylint:toolchain_type"))

def _py_pylint_toolchain_impl(ctx):
    pylint_target = ctx.attr.pylint

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = pylint_target[DefaultInfo].files,
        runfiles = pylint_target[DefaultInfo].default_runfiles,
    )

    return [
        platform_common.ToolchainInfo(
            pylint = ctx.attr.pylint,
        ),
        default_info,
        pylint_target[PyInfo],
        pylint_target[OutputGroupInfo],
        pylint_target[InstrumentedFilesInfo],
    ]

py_pylint_toolchain = rule(
    implementation = _py_pylint_toolchain_impl,
    doc = "A toolchain for the [pylint](https://pylint.readthedocs.io/en/stable/) formatter rules.",
    attrs = {
        "pylint": attr.label(
            doc = "The pylint `py_library` to use with the rules.",
            providers = [PyInfo],
            mandatory = True,
        ),
    },
)

def _current_py_pylint_toolchain_impl(ctx):
    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]

    pylint_target = toolchain.pylint

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = pylint_target[DefaultInfo].files,
        runfiles = pylint_target[DefaultInfo].default_runfiles,
    )

    return [
        toolchain,
        default_info,
        pylint_target[PyInfo],
        pylint_target[OutputGroupInfo],
        pylint_target[InstrumentedFilesInfo],
    ]

current_py_pylint_toolchain = rule(
    doc = "A rule for exposing the current registered `py_pylint_toolchain`.",
    implementation = _current_py_pylint_toolchain_impl,
    toolchains = [TOOLCHAIN_TYPE],
)
