"""Interfaces for rule authors to use in custom rules"""

load("@bazel_skylib//lib:paths.bzl", "paths")
load("@rules_python//python:defs.bzl", "PyInfo")

_TOOLCHAIN_TYPE = str(Label("//python/venv:toolchain_type"))

def _create_dep_info(*, ctx, deps):
    """Construct dependency info required for building `PyInfo`

    Args:
        ctx (ctx): The rule's context object.
        deps (list): A list of python dependency targets

    Returns:
        struct: Dependency info.
    """
    runfiles = ctx.runfiles()
    import_workspaces = []
    imports = []
    srcs = []
    for dep in deps:
        info = dep[PyInfo]
        srcs.append(info.transitive_sources)
        imports.append(info.imports)
        workspace_name = dep.label.workspace_name
        if not workspace_name:
            workspace_name = ctx.workspace_name
        import_workspaces.append(workspace_name)
        runfiles = runfiles.merge(dep[DefaultInfo].default_runfiles)

    return struct(
        # https://bazel.build/rules/lib/providers/PyInfo#imports
        transitive_imports = depset(import_workspaces, transitive = imports),
        # https://bazel.build/rules/lib/providers/PyInfo#transitive_sources
        transitive_sources = depset(transitive = srcs, order = "postorder"),
        # Runfiles from dependencies.
        runfiles = runfiles,
    )

def _get_imports(*, ctx, imports, transitive_imports):
    """Determine the import paths from a target's `imports` attribute.

    Args:
        ctx (ctx): The rule's context object.
        imports (list): A list of import paths.
        transitive_imports (depset): Resolved imports form transitive dependencies.

    Returns:
        depset: A set of the resolved import paths.
    """
    workspace_name = ctx.label.workspace_name
    if not workspace_name:
        workspace_name = ctx.workspace_name

    import_root = "{}/{}".format(workspace_name, ctx.label.package).rstrip("/")

    result = [workspace_name]
    for import_str in imports:
        import_str = ctx.expand_make_variables("imports", import_str, {})
        if import_str.startswith("/"):
            continue

        # To prevent "escaping" out of the runfiles tree, we normalize
        # the path and ensure it doesn't have up-level references.
        import_path = paths.normalize("{}/{}".format(import_root, import_str))
        if import_path.startswith("../") or import_path == "..":
            fail("Path '{}' references a path above the execution root".format(
                import_str,
            ))
        result.append(import_path)

    return depset(result, transitive = [transitive_imports])

def _create_py_info(*, ctx, imports, srcs, dep_info = None):
    """Construct a `PyInfo` provider

    Args:
        ctx (ctx): The rule's context object.
        imports (list): The raw `imports` attribute.
        srcs (list): A list of python (`.py`) source files.
        dep_info (struct, optional): Dependency info from the current target.

    Returns:
        PyInfo: A `PyInfo` provider.
    """
    if not dep_info:
        dep_info = _create_dep_info(ctx = ctx, deps = [])

    return PyInfo(
        # https://bazel.build/rules/lib/providers/PyInfo#imports
        imports = _get_imports(
            ctx = ctx,
            imports = imports,
            transitive_imports = dep_info.transitive_imports,
        ),
        # https://bazel.build/rules/lib/providers/PyInfo#transitive_sources
        transitive_sources = depset(
            srcs,
            transitive = [dep_info.transitive_sources],
            order = "postorder",
        ),
    )

def _create_venv_config_info(*, label, name, imports):
    """Construct info used to create venvs.

    Args:
        label (Label): The label of the target that owns the venv.
        name (str): The name for the venv.
        imports (List): A list of import paths to write to `.pth` files.

    Returns:
        struct: the data.
    """
    pth_data = [
        "{{runfiles_dir}}/{}".format(import_dir)
        for import_dir in imports
    ]
    return struct(
        label = str(label),
        name = name,
        pth = pth_data,
    )

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _path(file, _workspace_name):
    return file.path

def _create_python_startup_args(*, ctx, version_info):
    """Construct an Args object for running python scripts.

    A python script can be added to the resulting Args object to spawn
    a process for it.

    Args:
        ctx (ctx): The rule's context object.
        version_info (struct): Python version info from `py_toolchain`.

    Returns:
        Args: An args object.
    """
    python_args = ctx.actions.args()
    python_args.add("-B")  # don't write .pyc files on import; also PYTHONDONTWRITEBYTECODE=x
    python_args.add("-s")  # don't add user site directory to sys.path; also PYTHONNOUSERSITE

    if (version_info.major >= 3 and version_info.minor >= 11) or version_info.major > 3:
        python_args.add("-P")  # safe paths (available in Python 3.11)

    return python_args

def _zip_resource_set(_os_name, inputs):
    return {
        # A somewhat arbitrary value but chosen to handle a 1GB zip
        # with 37000 files in it. Some of which are C extensions
        # some are simple python files.
        "memory": 0.55 * inputs,
    }

def _create_runfiles_collection(*, ctx, venv_toolchain, py_toolchain, runfiles, name = None):
    """Generate a runfiles directory

    This functionality exists due to the lack of native support for generating
    runfiles in an action. For details see: https://github.com/bazelbuild/bazel/issues/15486

    Args:
        ctx (ctx): The rule's context object.
        venv_toolchain (ToolchainInfo): A `py_venv_toolchain` toolchain.
        py_toolchain (ToolchainInfo): A `py_toolchain` toolchain.
        runfiles (Runfiles): The runfiles to render into a directory
        name (str, optional): An alternate name to use in the output instead of `ctx.label.name`.

    Returns:
        File: The generated runfiles directory.
    """

    py_runtime = py_toolchain.py3_runtime
    interpreter = None
    if py_runtime.interpreter:
        interpreter = py_runtime.interpreter

    if not interpreter:
        fail("Unable to locate interpreter from py_toolchain: {}".format(py_toolchain))

    if name == None:
        name = ctx.label.name

    output = ctx.actions.declare_file("{}.venv_runfiles.zip".format(name))

    python_args = _create_python_startup_args(ctx = ctx, version_info = py_runtime.interpreter_version_info)

    python_args.add(venv_toolchain.runfiles_maker)

    python_args.add("--output", output)

    runfiles_args = ctx.actions.args()
    runfiles_args.use_param_file("@%s", use_always = True)

    py_runtime_files = {file: None for file in py_runtime.files.to_list()}

    workspace_name = ctx.workspace_name

    def _runfiles_filter_map(file):
        if file in py_runtime_files:
            return None
        return "{}={}".format(file.path, _rlocationpath(file, workspace_name))

    runfiles_args.add_all(runfiles.files, map_each = _runfiles_filter_map, allow_closure = True)

    ctx.actions.run(
        mnemonic = "PyVenvRunfiles",
        executable = interpreter,
        tools = depset(
            [
                venv_toolchain.runfiles_maker,
            ],
            transitive = [
                py_runtime.files,
            ],
        ),
        outputs = [output],
        inputs = runfiles.files,
        arguments = [python_args, runfiles_args],
        env = ctx.configuration.default_shell_env,
        resource_set = _zip_resource_set,
    )

    return output

def _create_venv_entrypoint(
        *,
        ctx,
        venv_toolchain,
        py_info,
        main,
        runfiles,
        py_toolchain = None,
        name = None,
        use_runfiles_in_entrypoint = True,
        force_runfiles = False):
    """Create an executable which constructs a python venv and subprocesses a given entrypoint.

    Args:
        ctx (ctx): The rule's context object.
        venv_toolchain (ToolchainInfo): A `py_venv_toolchain` toolchain.
        py_info (PyInfo): The `PyInfo` provider for the current target.
        main (File): The main python entrypoint.
        runfiles (Runfiles): Runfiles associated with the executable.
        py_toolchain (ToolchainInfo, optional): A `py_toolchain` toolchain. If one is not
            provided one will be acquired via `py_venv_toolchain`.
        name (str, optional): An alternate name to use in the output instead of `ctx.label.name`.
        use_runfiles_in_entrypoint (bool, optional): If true, an entrypoint will be created that
            relies on runfiles.
        force_runfiles (bool, optional): If True, a rendered runfiles directory will be used over
            builtin runfiles where `RUNFILES_DIR` would be provided.

    Returns:
        Tuple[File, Runfiles]: The generated entrypoint and associated runfiles.
    """
    if py_toolchain == None:
        py_toolchain = venv_toolchain.py_toolchain

    workspace_name = ctx.workspace_name

    if use_runfiles_in_entrypoint:
        path_fn = _rlocationpath
    else:
        path_fn = _path

    py_runtime = py_toolchain.py3_runtime
    interpreter = None
    if py_runtime.interpreter:
        interpreter = path_fn(py_runtime.interpreter, workspace_name)
    else:
        interpreter = py_runtime.interpreter_path

    if not interpreter:
        fail("Unable to locate interpreter from py_toolchain: {}".format(py_toolchain))

    if name == None:
        name = ctx.label.name
    is_windows = venv_toolchain.entrypoint.basename.endswith(".bat")
    entrypoint = ctx.actions.declare_file("{}.{}".format(name, "bat" if is_windows else "sh"))

    venv_config_info = _create_venv_config_info(
        label = ctx.label,
        name = name.replace("/", "_"),
        imports = py_info.imports.to_list(),
    )

    venv_config = ctx.actions.declare_file("{}.venv_config.json".format(name))
    ctx.actions.write(
        output = venv_config,
        content = json.encode_indent(
            venv_config_info,
            indent = " " * 4,
        ),
    )

    venv_runfiles = ctx.runfiles(transitive_files = depset(transitive = [
        depset([
            venv_toolchain.process_wrapper,
            venv_config,
        ]),
        py_runtime.files,
        py_info.transitive_sources,
    ])).merge(runfiles)

    runfiles_path = ""
    if force_runfiles or not venv_toolchain.runfiles_enabled:
        runfiles_collection = _create_runfiles_collection(
            ctx = ctx,
            venv_toolchain = venv_toolchain,
            py_toolchain = py_toolchain,
            runfiles = venv_runfiles,
            name = name,
        )
        runfiles_path = path_fn(runfiles_collection, workspace_name)
        venv_runfiles = venv_runfiles.merge(ctx.runfiles(files = [
            runfiles_collection,
        ]))

    ctx.actions.expand_template(
        output = entrypoint,
        template = venv_toolchain.entrypoint,
        substitutions = {
            "{MAIN}": path_fn(main, workspace_name),
            "{PY_RUNTIME}": interpreter,
            "{USE_RUNFILES}": "1" if use_runfiles_in_entrypoint else "0",
            "{VENV_CONFIG}": path_fn(venv_config, workspace_name),
            "{VENV_PROCESS_WRAPPER}": path_fn(venv_toolchain.process_wrapper, workspace_name),
            "{VENV_RUNFILES_COLLECTION}": runfiles_path,
        },
        is_executable = True,
    )

    venv_runfiles = venv_runfiles.merge(ctx.runfiles(files = [
        main,
    ]))

    return entrypoint, venv_runfiles

def _create_venv_attrs():
    return {
        "_py_venv_toolchain": attr.label(
            doc = "A py_venv_toolchain in the exec configuration.",
            cfg = "exec",
            default = Label("//python/venv:current_py_venv_toolchain"),
        ),
    }

def _get_py_venv_toolchain(ctx, *, cfg = "target"):
    if cfg == "target":
        return ctx.toolchains[_TOOLCHAIN_TYPE]
    if cfg == "exec":
        if not hasattr(ctx.attr, "_py_venv_toolchain"):
            fail("`py_venv_common.get_py_venv_toolchain` requires that the rule for `{}` has attributes from `py_venv_common.create_venv_attrs`.".format(
                ctx.label,
            ))
        toolchain = ctx.attr._py_venv_toolchain[platform_common.ToolchainInfo]
        return toolchain
    fail("Unepxected configuration for {}: `cfg = {}`".format(
        ctx.label,
        cfg,
    ))

def _create_python_zip_file(
        *,
        ctx,
        venv_toolchain,
        py_info,
        main,
        runfiles,
        py_toolchain = None,
        name = None):
    """Create a zipapp.

    Args:
        ctx (ctx): The rule's context object.
        venv_toolchain (ToolchainInfo): A `py_venv_toolchain` toolchain.
        py_info (PyInfo): The `PyInfo` provider for the current target.
        main (File): The main python entrypoint.
        runfiles (Runfiles): Runfiles associated with the executable.
        py_toolchain (ToolchainInfo, optional): A `py_toolchain` toolchain. If one is not
            provided one will be acquired via `py_venv_toolchain`.
        name (str, optional): An alternate name to use in the output instead of `ctx.label.name`.

    Returns:
        File: The generated zip file.
    """
    if py_toolchain == None:
        py_toolchain = venv_toolchain.py_toolchain

    py_runtime = py_toolchain.py3_runtime
    interpreter = None
    if py_runtime.interpreter:
        interpreter = py_runtime.interpreter

    if not interpreter:
        fail("Unable to locate interpreter from py_toolchain: {}".format(py_toolchain))

    if name == None:
        name = ctx.label.name

    venv_config_info = _create_venv_config_info(
        label = ctx.label,
        name = name.replace("/", "_"),
        imports = py_info.imports.to_list(),
    )

    venv_runfiles = ctx.runfiles(transitive_files = depset(transitive = [
        depset([
            main,
            venv_toolchain.process_wrapper,
        ]),
        py_runtime.files,
        py_info.transitive_sources,
    ])).merge(runfiles)

    python_zip_file = ctx.actions.declare_file("{}.pyz".format(name))

    python_args = _create_python_startup_args(ctx = ctx, version_info = py_runtime.interpreter_version_info)
    python_args.add(venv_toolchain.zipapp_maker)
    args = ctx.actions.args()
    args.add("--zipapp_main_template", venv_toolchain.zipapp_main)
    args.add("--main", _rlocationpath(main, ctx.workspace_name))
    args.add("--py_runtime", _rlocationpath(interpreter, ctx.workspace_name))
    args.add("--venv_process_wrapper", _rlocationpath(venv_toolchain.process_wrapper, ctx.workspace_name))
    if venv_toolchain.zipapp_shebang:
        args.add("--shebang", venv_toolchain.zipapp_main)
    args.add("--output", python_zip_file)
    args.add("--venv_config_info", json.encode(venv_config_info))

    workspace_name = ctx.workspace_name

    def _runfiles_filter_map(file):
        return "{}={}".format(file.path, _rlocationpath(file, workspace_name))

    args.add_all(venv_runfiles.files, map_each = _runfiles_filter_map, format_each = "--rfile=%s", allow_closure = True)

    args.use_param_file("@%s", use_always = True)
    args.set_param_file_format("multiline")

    ctx.actions.run(
        mnemonic = "PyVenvZipapp",
        executable = interpreter,
        arguments = [python_args, args],
        outputs = [python_zip_file],
        inputs = depset([main, venv_toolchain.zipapp_main], transitive = [venv_runfiles.files]),
        tools = depset([venv_toolchain.zipapp_maker], transitive = [py_runtime.files]),
        env = ctx.configuration.default_shell_env,
        resource_set = _zip_resource_set,
    )

    return python_zip_file

py_venv_common = struct(
    create_dep_info = _create_dep_info,
    create_py_info = _create_py_info,
    create_python_zip_file = _create_python_zip_file,
    create_runfiles_collection = _create_runfiles_collection,
    create_venv_attrs = _create_venv_attrs,
    create_venv_entrypoint = _create_venv_entrypoint,
    get_toolchain = _get_py_venv_toolchain,
    TOOLCHAIN_TYPE = _TOOLCHAIN_TYPE,
)
