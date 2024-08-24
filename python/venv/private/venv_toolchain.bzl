"""Bazel rules for Python venvs"""

load(":runfiles_enabled.bzl", "is_runfiles_enabled", "runfiles_enabled_attr")

def _py_venv_toolchain_impl(ctx):
    all_files = []
    all_files.append(ctx.attr._entrypoint[DefaultInfo].default_runfiles.files)

    py_toolchain = ctx.toolchains[Label("@rules_python//python:toolchain_type")]

    return [platform_common.ToolchainInfo(
        all_files = depset(transitive = all_files),
        entrypoint = ctx.file._entrypoint,
        process_wrapper = ctx.file._process_wrapper,
        py_toolchain = py_toolchain,
        runfiles_enabled = is_runfiles_enabled(ctx.attr),
        runfiles_maker = ctx.file._runfiles_maker,
        zipapp_shebang = ctx.attr.zipapp_shebang,
        zipapp_maker = ctx.file._zipapp_maker,
        zipapp_main = ctx.file._zipapp_main,
    )]

py_venv_toolchain = rule(
    doc = "Declare a toolchain for `rules_venv` rules.",
    implementation = _py_venv_toolchain_impl,
    attrs = {
        "zipapp_shebang": attr.string(
            doc = "The shebang to use when creating zipapps (`OutputGroupInfo.python_zip_file`).",
        ),
        "_entrypoint": attr.label(
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/venv/private:venv_entrypoint"),
        ),
        "_process_wrapper": attr.label(
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/venv/private:venv_process_wrapper.py"),
        ),
        "_runfiles_maker": attr.label(
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/venv/private:venv_runfiles.py"),
        ),
        "_zipapp_main": attr.label(
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/venv/private:venv_zipapp_main.py"),
        ),
        "_zipapp_maker": attr.label(
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/venv/private:venv_zipapp_maker.py"),
        ),
    } | runfiles_enabled_attr(
        cfg = "exec",
        default = Label("//python/venv/private:runfiles_enabled"),
    ),
    toolchains = [
        str(Label("@rules_python//python:toolchain_type")),
    ],
)

def _current_py_venv_toolchain_impl(ctx):
    toolchain = ctx.toolchains[Label("//python/venv:toolchain_type")]

    return [
        toolchain,
    ]

current_py_venv_toolchain = rule(
    doc = "Access the `py_venv_toolchain` for the current configuration.",
    implementation = _current_py_venv_toolchain_impl,
    toolchains = [str(Label("//python/venv:toolchain_type"))],
)
