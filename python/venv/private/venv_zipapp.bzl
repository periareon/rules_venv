"""Rules for producing zipapps"""

load("@rules_python//python:defs.bzl", "PyInfo")
load(":venv.bzl", "PyMainInfo", "compute_main")
load(":venv_common.bzl", "create_python_zip_file", venv_common = "py_venv_common")

ArgvInheritInfo = provider(
    doc = "A provider for extracting args and envs to imbed in zipapps.",
    fields = {
        "args": "List[str]: Template variable expanded arguments",
        "env": "Dict[str, str]: Template variable expanded environment variables.",
    },
)

def _argv_inherit_aspect_impl(_target, ctx):
    targets = getattr(ctx.rule.attr, "data", [])
    known_variables = {}
    for target in getattr(ctx.rule.files, "toolchains", []):
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

    return [ArgvInheritInfo(
        args = expanded_args,
        env = expanded_env,
    )]

_argv_inherit_aspect = aspect(
    doc = "TODO",
    implementation = _argv_inherit_aspect_impl,
)

def _py_venv_zipapp_impl(ctx):
    venv_toolchain = ctx.toolchains[venv_common.TOOLCHAIN_TYPE]
    py_info = ctx.attr.binary[PyInfo]
    main_info = ctx.attr.binary[PyMainInfo]

    inject_args = []
    inject_env = {}
    argv_info = ctx.attr.binary[ArgvInheritInfo]
    if ctx.attr.inherit_args:
        inject_args.extend(argv_info.args)
    if ctx.attr.inherit_env:
        inject_env.update(argv_info.env)
    inject_args.extend(ctx.attr.args)
    inject_env.update(ctx.attr.env)

    python_zip_file = create_python_zip_file(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = compute_main(
            ctx = ctx,
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
            aspects = [_argv_inherit_aspect],
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
