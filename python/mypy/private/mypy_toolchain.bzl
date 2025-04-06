"""mypy toolchain rules."""

load("//python:py_info.bzl", "PyInfo")

TOOLCHAIN_TYPE = str(Label("//python/mypy:toolchain_type"))

def _py_mypy_toolchain_impl(ctx):
    mypy_target = ctx.attr.mypy

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = mypy_target[DefaultInfo].files,
        runfiles = mypy_target[DefaultInfo].default_runfiles,
    )

    return [
        platform_common.ToolchainInfo(
            mypy = ctx.attr.mypy,
        ),
        default_info,
        mypy_target[PyInfo],
        mypy_target[OutputGroupInfo],
        mypy_target[InstrumentedFilesInfo],
    ]

py_mypy_toolchain = rule(
    implementation = _py_mypy_toolchain_impl,
    doc = "A toolchain for the [mypy](https://mypy.readthedocs.io/) formatter rules.",
    attrs = {
        "mypy": attr.label(
            doc = "The mypy `py_library` to use with the rules.",
            providers = [PyInfo],
            mandatory = True,
        ),
    },
)

def _current_py_mypy_toolchain_impl(ctx):
    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]

    mypy_target = toolchain.mypy

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = mypy_target[DefaultInfo].files,
        runfiles = mypy_target[DefaultInfo].default_runfiles,
    )

    return [
        toolchain,
        default_info,
        mypy_target[PyInfo],
        mypy_target[OutputGroupInfo],
        mypy_target[InstrumentedFilesInfo],
    ]

current_py_mypy_toolchain = rule(
    doc = "A rule for exposing the current registered `py_mypy_toolchain`.",
    implementation = _current_py_mypy_toolchain_impl,
    toolchains = [TOOLCHAIN_TYPE],
)
