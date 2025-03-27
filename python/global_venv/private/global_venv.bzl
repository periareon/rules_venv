"""Utilities for setting up a venv with all available Bazel targets"""

load("@rules_python//python:defs.bzl", "PyInfo")
load("//python/venv:defs.bzl", "py_venv_binary")

def global_venv(name, **kwargs):
    """Define a "global venv" executable.

    Args:
        name (str): The name of the target
        **kwargs (dict): Additional keyword arguments for the `py_venv_binary`.
    """
    main = Label("//python/global_venv/private:global_venv.py")

    py_venv_binary(
        name = name,
        srcs = [main],
        main = main,
        **kwargs
    )

PyGlobalVenvInfo = provider(
    doc = "Info about a python package required to include it in a global venv.",
    fields = {
        "bin_dir": "Optional[String]: The path to the bin dir (signifies the current configuration).",
        "imports": "File: A json encoded file.",
    },
)

SPEC_FILE_SUFFIX = ".py_global_venv_info.json"

def _is_py_source(file):
    return file.basename.endswith((".py", ".pyi", ".so", ".pyd", ".pyc"))

def _py_global_venv_aspect_impl(target, ctx):
    info = target[PyInfo]
    data = {
        "bin_dir": None,
        "imports": info.imports.to_list(),
    }

    has_generated_files = bool(not all([
        src.is_source
        for src in target[DefaultInfo].files.to_list()
        if _is_py_source(src)
    ]))

    if has_generated_files:
        data["bin_dir"] = ctx.bin_dir.path

    output = ctx.actions.declare_file("{}{}".format(target.label.name, SPEC_FILE_SUFFIX))
    ctx.actions.write(
        output = output,
        content = json.encode_indent(data, indent = " " * 4) + "\n",
    )

    return [
        OutputGroupInfo(
            py_global_venv_info = depset([output]),
        ),
        PyGlobalVenvInfo(**data),
    ]

py_global_venv_aspect = aspect(
    doc = "An aspect for generating metadata required to include Python targets in a global venv.",
    implementation = _py_global_venv_aspect_impl,
    required_providers = [PyInfo],
)
