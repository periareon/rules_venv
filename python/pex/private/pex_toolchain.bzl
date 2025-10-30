"""pex toolchain rules."""

load("//python:py_info.bzl", "PyInfo")

TOOLCHAIN_TYPE = str(Label("//python/pex:toolchain_type"))

def _py_pex_toolchain_impl(ctx):
    pex_target = ctx.attr.pex

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with the same info.
    default_info = DefaultInfo(
        files = pex_target[DefaultInfo].files,
        runfiles = pex_target[DefaultInfo].default_runfiles,
    )

    platform = None
    if ctx.attr.platform:
        platform = ctx.attr.platform

    return [
        platform_common.ToolchainInfo(
            pex = pex_target,
            scie_science = ctx.file.scie_science,
            platform = platform,
        ),
        default_info,
        pex_target[PyInfo],
        pex_target[OutputGroupInfo],
        pex_target[InstrumentedFilesInfo],
    ]

py_pex_toolchain = rule(
    implementation = _py_pex_toolchain_impl,
    doc = "A toolchain for the [pex](https://github.com/pantsbuild/pex) packaging tool rules.",
    attrs = {
        "pex": attr.label(
            doc = "The pex `py_library` to use with the rules.",
            providers = [PyInfo],
            mandatory = True,
            cfg = "exec",
        ),
        "platform": attr.string(
            doc = "The platform to target for scie executables.",
            mandatory = True,
        ),
        "scie_science": attr.label(
            doc = "The scie science binary to use for scie targets.",
            allow_single_file = True,
            executable = True,
            cfg = "target",
            mandatory = True,
        ),
    },
)

def _current_py_pex_toolchain_impl(ctx):
    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]

    pex_target = toolchain.pex

    # For some reason, simply forwarding `DefaultInfo` from
    # the target results in a loss of data. To avoid this a
    # new provider is created with the same info.
    default_info = DefaultInfo(
        files = pex_target[DefaultInfo].files,
        runfiles = pex_target[DefaultInfo].default_runfiles,
    )

    return [
        toolchain,
        default_info,
        pex_target[PyInfo],
        pex_target[OutputGroupInfo],
        pex_target[InstrumentedFilesInfo],
    ]

current_py_pex_toolchain = rule(
    doc = "A rule for exposing the current registered `py_pex_toolchain`.",
    implementation = _current_py_pex_toolchain_impl,
    toolchains = [TOOLCHAIN_TYPE],
)
