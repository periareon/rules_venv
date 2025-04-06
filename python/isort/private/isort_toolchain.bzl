"""isort toolchain rules."""

load("//python:py_info.bzl", "PyInfo")

TOOLCHAIN_TYPE = str(Label("//python/isort:toolchain_type"))

def _py_isort_toolchain_impl(ctx):
    isort_target = ctx.attr.isort

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = isort_target[DefaultInfo].files,
        runfiles = isort_target[DefaultInfo].default_runfiles,
    )

    return [
        platform_common.ToolchainInfo(
            isort = ctx.attr.isort,
        ),
        default_info,
        isort_target[PyInfo],
        isort_target[OutputGroupInfo],
        isort_target[InstrumentedFilesInfo],
    ]

py_isort_toolchain = rule(
    implementation = _py_isort_toolchain_impl,
    doc = "A toolchain for the [isort](https://pycqa.github.io/isort/index.html) formatter rules.",
    attrs = {
        "isort": attr.label(
            doc = "The isort `py_library` to use with the rules.",
            providers = [PyInfo],
            mandatory = True,
        ),
    },
)

def _current_py_isort_toolchain_impl(ctx):
    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]

    isort_target = toolchain.isort

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with teh same info.
    default_info = DefaultInfo(
        files = isort_target[DefaultInfo].files,
        runfiles = isort_target[DefaultInfo].default_runfiles,
    )

    return [
        toolchain,
        default_info,
        isort_target[PyInfo],
        isort_target[OutputGroupInfo],
        isort_target[InstrumentedFilesInfo],
    ]

current_py_isort_toolchain = rule(
    doc = "A rule for exposing the current registered `py_isort_toolchain`.",
    implementation = _current_py_isort_toolchain_impl,
    toolchains = [TOOLCHAIN_TYPE],
)
