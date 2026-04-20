"""Utilities for setting up a venv with all available Bazel targets"""

load("//python:py_info.bzl", "PyInfo")
load("//python/venv:defs.bzl", "py_venv_binary")

def py_global_venv(
        *,
        name,
        gen_pyrightconfig = True,
        gen_entrypoints = True,
        entrypoints = {},
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

    **Important:** Do not define ``extraPaths`` in your own ``pyrightconfig.json``
    when using ``extends``. Pyright's ``extends`` replaces array fields rather
    than merging them, so any ``extraPaths`` in the child config will override
    the generated values from ``bazel-pyrightconfig.json``.

    When targets use configuration transitions (e.g. ``py_cc_extension`` building
    with ``compilation_mode = "opt"``), generated files may live in directories
    like ``bazel-out/k8-opt/bin`` instead of ``bazel-out/k8-fastbuild/bin``. The
    generated ``bazel-pyrightconfig.json`` includes all observed output directories
    automatically.

    For **ruff** or **isort** to correctly classify first-party imports that
    include generated sources, add the Bazel output directories to the ``src``
    setting::

    ```toml
    # .ruff.toml
    src = [".", "bazel-out/k8-*/bin"]
    ```

    For standalone **isort**::

    ```ini
    # .isort.cfg
    [isort]
    src_paths = .,bazel-out/k8-*/bin
    ```

    This allows ruff/isort to find generated ``.pyi`` stubs and ``.so`` extensions
    when determining whether an import is first-party or third-party.

    When ``gen_entrypoints`` is enabled (the default), running this target will
    auto-discover ``console_scripts`` entrypoints from pip packages via
    ``importlib.metadata`` and generate executable scripts in the venv's ``bin/``
    directory. Pre-built binaries shipped via wheel data scripts (e.g. ``ruff``)
    are also symlinked into the venv. This allows IDEs to find tools like
    ``black``, ``ruff``, or ``mypy`` inside the venv. Additional entrypoints can
    be specified manually via ``entrypoints``.

    Args:
        name (str): The name of the target
        gen_pyrightconfig (bool): Generate a `bazel-pyrightconfig.json` to support indexing
            Bazel generated files.
        gen_entrypoints (bool): Auto-discover `console_scripts` entrypoints from pip
            packages and generate executable scripts in the venv `bin/` directory.
        entrypoints (dict): A mapping of script names to module specs
            (e.g. `{"black": "black:patched_main"}`). These are always rendered regardless
            of `gen_entrypoints`. When `gen_entrypoints` is also enabled, manual
            entries take precedence over auto-discovered ones.
        build_srcs (bool): Build all python sources to ensure they're available for loading.
        **kwargs (dict): Additional keyword arguments for the `py_venv_binary`.
    """
    main = Label("//python/global_venv/private:global_venv.py")

    args = []
    if gen_pyrightconfig:
        args.append("--gen_pyrightconfig")

    if gen_entrypoints:
        args.append("--gen_entrypoints")

    for ep_name, ep_spec in entrypoints.items():
        args.extend(["--entrypoint", "{}={}".format(ep_name, ep_spec)])

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
        "bin_dirs": "List[String]: The paths to the bin dirs for each unique configuration.",
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

    # Collect any additional runfiles but only ones owned by the current targt
    runfiles = depset([
        file
        for file in target[DefaultInfo].default_runfiles.files.to_list()
        if file.owner == target.label
    ])

    all_files = [target[DefaultInfo].files]
    all_files.append(runfiles)
    all_files.extend(_collect_files(getattr(ctx.rule.attr, "srcs", [])))
    all_files.extend(_collect_files(getattr(ctx.rule.attr, "data", [])))
    all_files = depset(transitive = all_files)

    generated_srcs = [
        src
        for src in all_files.to_list()
        if _is_py_source(src) and not src.is_source
    ]

    bin_dirs = {src.root.path: True for src in generated_srcs}

    data = {
        "bin_dirs": sorted(bin_dirs.keys()),
        "imports": info.imports.to_list(),
    }

    output = ctx.actions.declare_file("{}{}".format(target.label.name, SPEC_FILE_SUFFIX))
    ctx.actions.write(
        output = output,
        content = json.encode_indent(data, indent = " " * 4) + "\n",
    )

    return [
        OutputGroupInfo(
            py_global_venv_info = depset([output]),
            py_global_venv_files = depset(generated_srcs),
        ),
        PyGlobalVenvInfo(**data),
    ]

py_global_venv_aspect = aspect(
    doc = "An aspect for generating metadata required to include Python targets in a global venv.",
    implementation = _py_global_venv_aspect_impl,
    required_providers = [PyInfo],
)
