"""black toolchain rules."""

load("//python:defs.bzl", "PyInfo")

TOOLCHAIN_TYPE = str(Label("//python/black:toolchain_type"))

def _py_black_toolchain_impl(ctx):
    black_target = ctx.attr.black

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with the same info.
    default_info = DefaultInfo(
        files = black_target[DefaultInfo].files,
        runfiles = black_target[DefaultInfo].default_runfiles,
    )

    return [
        platform_common.ToolchainInfo(
            black = ctx.attr.black,
        ),
        default_info,
        black_target[PyInfo],
        black_target[OutputGroupInfo],
        black_target[InstrumentedFilesInfo],
    ]

py_black_toolchain = rule(
    implementation = _py_black_toolchain_impl,
    doc = "A toolchain for the [black](https://black.readthedocs.io/en/stable/) formatter rules.",
    attrs = {
        "black": attr.label(
            doc = "The black `py_library` to use with the rules.",
            providers = [PyInfo],
            mandatory = True,
        ),
    },
)

def _current_py_black_toolchain_impl(ctx):
    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]

    black_target = toolchain.black

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = black_target[DefaultInfo].files,
        runfiles = black_target[DefaultInfo].default_runfiles,
    )

    return [
        toolchain,
        default_info,
        black_target[PyInfo],
        black_target[OutputGroupInfo],
        black_target[InstrumentedFilesInfo],
    ]

current_py_black_toolchain = rule(
    doc = "A rule for exposing the current registered `py_black_toolchain`.",
    implementation = _current_py_black_toolchain_impl,
    toolchains = [TOOLCHAIN_TYPE],
)
