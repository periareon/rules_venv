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
            config = ctx.file.config,
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
        "config": attr.label(
            doc = """\
The config file (`mypy.ini`) containing mypy settings.

Settings and mypy version together decide what a cache entry means, so
they are named in one place. The default tracks the
`@rules_venv//python/mypy:config` flag, which is how a workspace that has not
defined its own toolchain chooses a config file.""",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/mypy:config"),
        ),
        "mypy": attr.label(
            doc = """\
The mypy `py_library` to use with the rules.

Must be mypy 2.0 or newer. These rules analyze a dependency once and share
the result with everything that imports it, which rests on mypy checking
function bodies only where the errors are wanted -- a split mypy grew in
2.0. An older release is refused rather than tolerated, since on a large
dependency the difference is seconds against half an hour.""",
            cfg = "exec",
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
