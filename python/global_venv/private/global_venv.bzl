"""Utilities for setting up a venv with all available Bazel targets"""

load("//python:py_info.bzl", "PyInfo")
load("//python/venv:defs.bzl", "py_venv_binary")

def py_global_venv(
        *,
        name,
        gen_pyrightconfig = True,
        build_srcs = False,
        **kwargs):
    """Define a "global venv" executable.

    When ``gen_pyrightconfig`` is enabled (the default), running this target
    writes a ``bazel-pyrightconfig.json`` at the workspace root containing
    ``extraPaths`` that point into ``bazel-bin``. This lets Pyright/Pylance
    resolve generated Python sources that live outside the source tree.

    To use it, add an ``extends`` field to your ``pyrightconfig.json``::

    ```json
    {
        "extends": "bazel-pyrightconfig.json",
        ...
    }
    ```

    Args:
        name (str): The name of the target
        gen_pyrightconfig (bool): Generate a `bazel-pyrightconfig.json` to support indexing
            Bazel generated files.
        build_srcs (bool): Build all python sources to ensure they're available for loading.
        **kwargs (dict): Additional keyword arguments for the `py_venv_binary`.
    """
    main = Label("//python/global_venv/private:global_venv.py")

    args = []
    if gen_pyrightconfig:
        args.append("--gen_pyrightconfig")

    if build_srcs:
        args.append("--build_srcs")

    py_venv_binary(
        name = name,
        srcs = [main],
        main = main,
        args = args,
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

def _collect_files(collection):
    all_files = []
    for entry in collection:
        if DefaultInfo in entry:
            all_files.extend([
                entry[DefaultInfo].files,
                entry[DefaultInfo].default_runfiles.files,
            ])
        elif type(entry) == "File":
            all_files.append(depset([entry]))

    return all_files

def _py_global_venv_aspect_impl(target, ctx):
    info = target[PyInfo]
    data = {
        "bin_dir": None,
        "imports": info.imports.to_list(),
    }

    all_files = [target[DefaultInfo].files]
    all_files.extend(_collect_files(getattr(ctx.rule.attr, "srcs", [])))
    all_files.extend(_collect_files(getattr(ctx.rule.attr, "data", [])))
    all_files = depset(transitive = all_files)

    generated_srcs = [
        src
        for src in all_files.to_list()
        if _is_py_source(src) and not src.is_source
    ]

    if generated_srcs:
        data["bin_dir"] = ctx.bin_dir.path

    output = ctx.actions.declare_file("{}{}".format(target.label.name, SPEC_FILE_SUFFIX))
    ctx.actions.write(
        output = output,
        content = json.encode_indent(data, indent = " " * 4) + "\n",
    )

    return [
        OutputGroupInfo(
            py_global_venv_info = depset([output]),
            py_global_venv_files = all_files,
        ),
        PyGlobalVenvInfo(**data),
    ]

py_global_venv_aspect = aspect(
    doc = "An aspect for generating metadata required to include Python targets in a global venv.",
    implementation = _py_global_venv_aspect_impl,
    required_providers = [PyInfo],
)
