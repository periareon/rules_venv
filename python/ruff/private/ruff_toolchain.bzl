"""ruff toolchain rules."""

load("//python:py_info.bzl", "PyInfo")

TOOLCHAIN_TYPE = str(Label("//python/ruff:toolchain_type"))

def rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _py_ruff_toolchain_impl(ctx):
    if ctx.attr.ruff and ctx.attr.ruff_bin:
        fail("`py_ruff_toolchain.ruff` and `py_ruff_toolchain.ruff_bin` are mutually exclusive. Please update {}".format(
            ctx.label,
        ))

    providers = []
    ruff_target = None
    ruff = None
    ruff_bin = None
    all_files = depset()
    template_variables = {}

    if ctx.attr.ruff:
        ruff_target = ctx.attr.ruff
        ruff = ctx.attr.ruff

        providers.extend([
            ruff_target[PyInfo],
            ruff_target[InstrumentedFilesInfo],
        ])

        template_variables["RUFF"] = ""
        template_variables["RUFF_RLOCATIONPATH"] = ""

    elif ctx.attr.ruff_bin:
        ruff_target = ctx.attr.ruff_bin
        ruff_bin = ctx.file.ruff_bin
        providers.append(
            PyInfo(
                imports = depset(),
                transitive_sources = depset(),
            ),
        )

        template_variables["RUFF"] = ruff_bin.path
        template_variables["RUFF_RLOCATIONPATH"] = rlocationpath(ruff_bin, ctx.workspace_name)

        all_files = depset(transitive = [
            ruff_target[DefaultInfo].files,
            ruff_target[DefaultInfo].default_runfiles.files,
        ])
    else:
        fail("`py_ruff_toolchain.ruff` or `py_ruff_toolchain.ruff_bin` are required. Please update {}".format(
            ctx.label,
        ))

    if OutputGroupInfo in ruff_target:
        providers.append(ruff_target[OutputGroupInfo])

    template_variable_info = platform_common.TemplateVariableInfo(
        template_variables,
    )

    return providers + [
        DefaultInfo(
            files = ruff_target[DefaultInfo].files,
            runfiles = ruff_target[DefaultInfo].default_runfiles,
        ),
        platform_common.ToolchainInfo(
            ruff = ruff,
            ruff_bin = ruff_bin,
            template_variable_info = template_variable_info,
            all_files = all_files,
        ),
        template_variable_info,
    ]

py_ruff_toolchain = rule(
    implementation = _py_ruff_toolchain_impl,
    doc = "A toolchain for the [ruff](https://docs.astral.sh/ruff/) linter and formatter rules.",
    attrs = {
        "ruff": attr.label(
            doc = "The ruff `py_library` with the rules.",
            providers = [PyInfo],
        ),
        "ruff_bin": attr.label(
            doc = "A `ruff` binary to use with the rules.",
            cfg = "exec",
            executable = True,
            allow_single_file = True,
        ),
    },
)

def _current_py_ruff_toolchain_impl(ctx):
    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]

    providers = [
        toolchain,
        toolchain.template_variable_info,
    ]

    if toolchain.ruff:
        providers.extend([
            # For some reason, simply forwarding `DefaultInfo` from
            # the target results in a loss of data. To avoid this a
            # new provider is created with the same info.
            DefaultInfo(
                files = toolchain.ruff[DefaultInfo].files,
                runfiles = toolchain.ruff[DefaultInfo].default_runfiles,
            ),
            toolchain.ruff[PyInfo],
            toolchain.ruff[OutputGroupInfo],
            toolchain.ruff[InstrumentedFilesInfo],
        ])

    else:
        providers.append(PyInfo(
            imports = depset(),
            transitive_sources = depset(),
        ))

    return providers

current_py_ruff_toolchain = rule(
    doc = "A rule for exposing the current registered `py_ruff_toolchain`.",
    implementation = _current_py_ruff_toolchain_impl,
    toolchains = [TOOLCHAIN_TYPE],
)
