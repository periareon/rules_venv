"""ty toolchain rules."""

load("//python:py_info.bzl", "PyInfo")

TOOLCHAIN_TYPE = str(Label("//python/ty:toolchain_type"))

def rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _py_ty_toolchain_impl(ctx):
    if ctx.attr.ty and ctx.attr.ty_bin:
        fail("`py_ty_toolchain.ty` and `py_ty_toolchain.ty_bin` are mutually exclusive. Please update {}".format(
            ctx.label,
        ))

    providers = []
    ty_target = None
    ty = None
    ty_bin = None
    all_files = depset()
    template_variables = {}

    if ctx.attr.ty:
        ty_target = ctx.attr.ty
        ty = ctx.attr.ty

        providers.extend([
            ty_target[PyInfo],
            ty_target[InstrumentedFilesInfo],
        ])

        template_variables["TY"] = ""
        template_variables["TY_RLOCATIONPATH"] = ""

    elif ctx.attr.ty_bin:
        ty_target = ctx.attr.ty_bin
        ty_bin = ctx.file.ty_bin
        providers.append(
            PyInfo(
                imports = depset(),
                transitive_sources = depset(),
            ),
        )

        template_variables["TY"] = ty_bin.path
        template_variables["TY_RLOCATIONPATH"] = rlocationpath(ty_bin, ctx.workspace_name)

        all_files = depset(transitive = [
            ty_target[DefaultInfo].files,
            ty_target[DefaultInfo].default_runfiles.files,
        ])
    else:
        fail("`py_ty_toolchain.ty` or `py_ty_toolchain.ty_bin` are required. Please update {}".format(
            ctx.label,
        ))

    if OutputGroupInfo in ty_target:
        providers.append(ty_target[OutputGroupInfo])

    template_variable_info = platform_common.TemplateVariableInfo(
        template_variables,
    )

    return providers + [
        DefaultInfo(
            files = ty_target[DefaultInfo].files,
            runfiles = ty_target[DefaultInfo].default_runfiles,
        ),
        platform_common.ToolchainInfo(
            ty = ty,
            ty_bin = ty_bin,
            template_variable_info = template_variable_info,
            all_files = all_files,
        ),
        template_variable_info,
    ]

py_ty_toolchain = rule(
    implementation = _py_ty_toolchain_impl,
    doc = "A toolchain for the [ty](https://docs.astral.sh/ty/) type checker rules.",
    attrs = {
        "ty": attr.label(
            doc = "The ty `py_library` to use with the rules.",
            providers = [PyInfo],
        ),
        "ty_bin": attr.label(
            doc = "A `ty` binary to use with the rules.",
            cfg = "exec",
            executable = True,
            allow_single_file = True,
        ),
    },
)

def _current_py_ty_toolchain_impl(ctx):
    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]

    providers = [
        toolchain,
        toolchain.template_variable_info,
    ]

    if toolchain.ty:
        providers.extend([
            DefaultInfo(
                files = toolchain.ty[DefaultInfo].files,
                runfiles = toolchain.ty[DefaultInfo].default_runfiles,
            ),
            toolchain.ty[PyInfo],
            toolchain.ty[OutputGroupInfo],
            toolchain.ty[InstrumentedFilesInfo],
        ])

    else:
        providers.append(PyInfo(
            imports = depset(),
            transitive_sources = depset(),
        ))

    return providers

current_py_ty_toolchain = rule(
    doc = "A rule for exposing the current registered `py_ty_toolchain`.",
    implementation = _current_py_ty_toolchain_impl,
    toolchains = [TOOLCHAIN_TYPE],
)
