"""Rules for producing zipapps"""

load("//python:py_info.bzl", "PyInfo")
load(":venv.bzl", "compute_main")
load(
    ":venv_common.bzl",
    "create_python_startup_args",
    "create_venv_config_info",
    "zip_resource_set",
    venv_common = "py_venv_common",
)

PyMainInfo = provider(
    doc = "`rules_venv` internal provider to inform consumers of binaries about their main entrypoint.",
    fields = {
        "args": "List[str]: Template variable expanded arguments",
        "data": "list[Target]: Data targets from the binary.",
        "env": "Dict[str, str]: Template variable expanded environment variables.",
        "main": "File: The main entrypoint for the target.",
        "srcs": "list[File]: The list of source files that directly belong to the binary.",
    },
)

def _py_main_aspect_impl(_target, ctx):
    targets = getattr(ctx.rule.attr, "data", [])
    known_variables = {}
    for target in getattr(ctx.rule.files, "toolchains", []):
        if type(target) != "Target":
            continue
        if platform_common.TemplateVariableInfo in target:
            variables = getattr(target[platform_common.TemplateVariableInfo], "variables", {})
            known_variables.update(variables)

    expanded_env = {}
    for key, value in getattr(ctx.rule.attr, "env", {}).items():
        expanded_env[key] = ctx.expand_make_variables(
            key,
            ctx.expand_location(value, targets),
            known_variables,
        )

    expanded_args = []
    for arg in getattr(ctx.rule.attr, "args", []):
        expanded_args.append(ctx.expand_make_variables(
            arg,
            ctx.expand_location(arg, targets),
            known_variables,
        ))

    workspace_name = ctx.label.workspace_name
    if not workspace_name:
        workspace_name = ctx.workspace_name

    if not workspace_name:
        workspace_name = "_main"

    # Needed for bzlmod-aware runfiles resolution.
    expanded_env["REPOSITORY_NAME"] = workspace_name

    return [PyMainInfo(
        main = getattr(ctx.rule.file, "main", None),
        srcs = getattr(ctx.rule.files, "srcs", []),
        data = targets,
        args = expanded_args,
        env = expanded_env,
    )]

py_main_aspect = aspect(
    doc = "An aspect used to collect arguments and environment variables from zipapp binaries.",
    implementation = _py_main_aspect_impl,
)

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def create_python_zip_file(
        *,
        ctx,
        venv_toolchain,
        py_info,
        main,
        inject_args,
        inject_env,
        runfiles,
        files_to_run,
        py_toolchain = None,
        py_toolchain_exec = None,
        shebang = None):
    """Create a zipapp.

    Args:
        ctx (ctx): The rule's context object.
        venv_toolchain (ToolchainInfo): A `py_venv_toolchain` toolchain.
        py_info (PyInfo): The `PyInfo` provider for the current target.
        main (File): The main python entrypoint.
        inject_args (list): A list of arguments to inject to the beginning of all zipapp invocations.
        inject_env (dict): A map of arguments to inject to the beginning of all zipapp invocations.
        runfiles (Runfiles): Runfiles associated with the executable.
        files_to_run (FilesToRunProvider): Files to run associated with the executable.
        py_toolchain (ToolchainInfo, optional): A `py_toolchain` toolchain. If one is not
            provided one will be acquired via `py_venv_toolchain`.
        py_toolchain_exec (ToolchainInfo, optional): A `py_toolchain` toolchain for the execution
            platform. If one is not provided one will be acquired via `py_venv_toolchain`.
        shebang (str, optional): Optional shebang contents to include, overriding the toolchain.
    Returns:
        File: The generated zip file.
    """
    if py_toolchain == None:
        py_toolchain = venv_toolchain.py_toolchain

    if py_toolchain_exec == None:
        py_toolchain_exec = venv_toolchain.py_toolchain_exec

    py_runtime = py_toolchain.py3_runtime
    interpreter = None
    if py_runtime.interpreter:
        interpreter = py_runtime.interpreter

    if not interpreter:
        fail("Unable to locate interpreter from py_toolchain: {}".format(py_toolchain))

    name = ctx.label.name
    if not name.endswith(".pyz"):
        name += ".pyz"

    venv_config_info = create_venv_config_info(
        label = ctx.label,
        name = name.replace("/", "_"),
        imports = py_info.imports.to_list(),
    )

    venv_runfiles = depset([
        main,
        venv_toolchain.process_wrapper,
        venv_toolchain.zipapp_main,
        files_to_run.runfiles_manifest,
        files_to_run.repo_mapping_manifest,
    ], transitive = [
        py_runtime.files,
        py_info.transitive_sources,
        runfiles.files,
    ])

    python_zip_file = ctx.actions.declare_file(name)

    python_args = create_python_startup_args(ctx = ctx, version_info = py_runtime.interpreter_version_info)
    python_args.add(venv_toolchain.zipapp_maker)
    args = ctx.actions.args()
    args.add("--zipapp_main_template", venv_toolchain.zipapp_main)
    args.add("--main", _rlocationpath(main, ctx.workspace_name))
    args.add("--py_runtime", _rlocationpath(interpreter, ctx.workspace_name))
    args.add("--venv_process_wrapper", _rlocationpath(venv_toolchain.process_wrapper, ctx.workspace_name))
    optional_shebang = shebang or venv_toolchain.zipapp_shebang
    if optional_shebang:
        args.add("--shebang", optional_shebang)
    args.add("--output", python_zip_file)
    args.add("--venv_config_info", json.encode(venv_config_info))
    args.add("--runfiles_manifest", files_to_run.runfiles_manifest)
    args.add("--inject_args", json.encode(inject_args))
    args.add("--inject_env", json.encode(inject_env))

    py_runtime_exec = py_toolchain_exec.py3_runtime
    interpreter_exec = None
    if py_runtime_exec.interpreter:
        interpreter_exec = py_runtime_exec.interpreter

    if not interpreter_exec:
        fail("Unable to locate interpreter (exec) from py_toolchain: {}".format(py_toolchain_exec))

    ctx.actions.run(
        mnemonic = "PyVenvZipapp",
        executable = interpreter_exec,
        arguments = [python_args, args],
        outputs = [python_zip_file],
        inputs = depset(transitive = [
            venv_runfiles,
            py_runtime_exec.files,
        ]),
        tools = [venv_toolchain.zipapp_maker],
        env = ctx.configuration.default_shell_env,
        resource_set = zip_resource_set,
        toolchain = venv_common.TOOLCHAIN_TYPE,
    )

    return python_zip_file

def _py_venv_zipapp_impl(ctx):
    venv_toolchain = ctx.toolchains[venv_common.TOOLCHAIN_TYPE]
    py_info = ctx.attr.binary[PyInfo]
    main_info = ctx.attr.binary[PyMainInfo]

    inject_args = []
    inject_env = {}
    if ctx.attr.inherit_args:
        inject_args.extend(main_info.args)
    if ctx.attr.inherit_env:
        inject_env.update(main_info.env)
    inject_args.extend(ctx.attr.args)
    inject_env.update(ctx.attr.env)

    python_zip_file = create_python_zip_file(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = compute_main(
            label = ctx.label,
            main = main_info.main,
            srcs = main_info.srcs,
        ),
        inject_args = inject_args,
        inject_env = inject_env,
        shebang = ctx.attr.shebang,
        runfiles = ctx.attr.binary[DefaultInfo].default_runfiles,
        files_to_run = ctx.attr.binary[DefaultInfo].files_to_run,
    )

    return [DefaultInfo(
        files = depset([python_zip_file]),
    )]

py_venv_zipapp = rule(
    doc = """\
A `py_venv_zipapp` is an executable [Python zipapp](https://docs.python.org/3/library/zipapp.html)
which contains all of the dependencies and runfiles for a given executable.

```python
load("@rules_venv//python/venv:defs.bzl", "py_venv_binary", "py_venv_zipapp")

py_venv_binary(
    name = "foo",
    srcs = ["foo.py"],
)

py_venv_zipapp(
    name = "foo_pyz",
    binary = ":foo",
)
```
""",
    implementation = _py_venv_zipapp_impl,
    attrs = {
        "args": attr.string_list(
            doc = "Arguments to add to the beginning of all invocations of the zipapp.",
        ),
        "binary": attr.label(
            doc = "The binary to package as a zipapp.",
            providers = [PyInfo],
            executable = True,
            cfg = "target",
            aspects = [py_main_aspect],
        ),
        "env": attr.string_dict(
            doc = "Environment variables to inject into all invocations of the zipapp.",
        ),
        "inherit_args": attr.bool(
            doc = "Inherit template variable expanded arguments from `binary`.",
            default = False,
        ),
        "inherit_env": attr.bool(
            doc = "Inherit template variable expanded environment variables from `binary`.",
            default = False,
        ),
        "shebang": attr.string(
            doc = "Optional shebang line to prepend to the zip (provided as content after `#!`).",
        ),
    },
    toolchains = [venv_common.TOOLCHAIN_TYPE],
)
