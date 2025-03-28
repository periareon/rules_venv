"""Bazel rules for isort"""

load("@bazel_skylib//lib:paths.bzl", "paths")
load("@rules_venv//python:defs.bzl", "PyInfo")
load("@rules_venv//python/venv:defs.bzl", "py_venv_common")

PyIsortInfo = provider(
    doc = "A provider containing information required by isort.",
    fields = {
        "imports": "Depset[str]: The values of `PyInfo.imports` for the current target.",
        "srcs": "Depset[File]: Formattable source files.",
    },
)

def _find_srcs(target, aspect_ctx = None):
    """Parse a target for it's sources to run on.

    Args:
        target (Target): The target the aspect is running on.
        aspect_ctx (ctx, optional): The aspect's context object.

    Returns:
        depset: A depset of sources (`File`).
    """
    if PyInfo not in target:
        return depset()

    # Ignore external targets
    if target.label.workspace_root.startswith("external"):
        return depset()

    # Sources are located differently based on whether or not
    # there's an aspect context object.
    if aspect_ctx:
        # Get a list of all non-generated source files.
        srcs = depset([
            src
            for src in getattr(aspect_ctx.rule.files, "srcs", [])
            if src.is_source
        ])

    elif PyIsortInfo in target:
        srcs = target[PyIsortInfo].srcs
    else:
        srcs = depset()

    return srcs

def _get_imports(target, aspect_ctx):
    """Gets the imports from a rule's `imports` attribute.

    See create_binary_semantics_struct for details about this function.

    Args:
        target (Target): The target the aspect is running on.
        aspect_ctx (ctx): The aspect's context object.

    Returns:
        List of strings.
    """
    workspace_name = target.label.workspace_name
    if not workspace_name:
        workspace_name = aspect_ctx.workspace_name

    prefix = "{}/{}".format(
        workspace_name,
        target.label.package,
    )
    result = []
    for import_str in getattr(aspect_ctx.rule.attr, "imports", []):
        import_str = aspect_ctx.expand_make_variables("imports", import_str, {})
        if import_str.startswith("/"):
            continue

        # To prevent "escaping" out of the runfiles tree, we normalize
        # the path and ensure it doesn't have up-level references.
        import_path = paths.normalize("{}/{}".format(prefix, import_str))
        if import_path.startswith("../") or import_path == "..":
            fail("Path '{}' references a path above the execution root".format(
                import_str,
            ))
        result.append(import_path)

    return result

def _py_isort_target_aspect_impl(target, ctx):
    srcs = _find_srcs(target, aspect_ctx = ctx)

    # Only collect imports for the current workspace to indicate which paths
    # are known first party packages.
    workspace_name = target.label.workspace_name
    if workspace_name and workspace_name != ctx.workspace_name:
        return [PyIsortInfo(
            srcs = srcs,
            imports = depset(),
        )]

    if not workspace_name:
        workspace_name = "_main"

    imports = depset([workspace_name] + _get_imports(target, ctx))

    return [PyIsortInfo(
        srcs = srcs,
        imports = imports,
    )]

py_isort_target_aspect = aspect(
    implementation = _py_isort_target_aspect_impl,
    doc = "An aspect for gathering additional data on a lintable target.",
    provides = [PyIsortInfo],
)

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _py_isort_test_impl(ctx):
    venv_toolchain = ctx.toolchains[py_venv_common.TOOLCHAIN_TYPE]

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner, ctx.attr.target],
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._runner_main],
        dep_info = dep_info,
    )

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._runner_main,
        runfiles = dep_info.runfiles,
    )

    isort_info = ctx.attr.target[PyIsortInfo]

    args_file = ctx.actions.declare_file("{}.isort_args.txt".format(ctx.label.name))
    ctx.actions.write(
        output = args_file,
        content = "\n".join([
            "--settings-path",
            _rlocationpath(ctx.file.config, ctx.workspace_name),
        ] + [
            "--import={}".format(path)
            for path in isort_info.imports.to_list()
        ] + [
            "--src={}".format(_rlocationpath(src, ctx.workspace_name))
            for src in isort_info.srcs.to_list()
        ] + [
            "--",
            "--check-only",
            "--diff",
        ]),
    )

    return [
        DefaultInfo(
            files = depset([executable]),
            runfiles = runfiles.merge(
                ctx.runfiles(files = [ctx.file.config, args_file]),
            ),
            executable = executable,
        ),
        RunEnvironmentInfo(
            environment = {
                "PY_ISORT_RUNNER_ARGS_FILE": _rlocationpath(args_file, ctx.workspace_name),
            },
        ),
    ]

py_isort_test = rule(
    implementation = _py_isort_test_impl,
    doc = "A rule for running isort on a Python target.",
    attrs = {
        "config": attr.label(
            doc = "The config file (isort.cfg) containing isort settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/isort:config"),
        ),
        "target": attr.label(
            doc = "The target to run `isort` on.",
            providers = [PyInfo],
            mandatory = True,
            aspects = [py_isort_target_aspect],
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running isort.",
            cfg = "exec",
            default = Label("//python/isort/private:isort_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the isort runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/isort/private:isort_runner.py"),
        ),
    },
    toolchains = [py_venv_common.TOOLCHAIN_TYPE],
    test = True,
)

def _py_isort_aspect_impl(target, ctx):
    ignore_tags = [
        "no_format",
        "no_isort_fmt",
        "no_isort_format",
        "no_isort",
        "noformat",
        "noisort",
    ]
    for tag in ctx.rule.attr.tags:
        sanitized = tag.replace("-", "_").lower()
        if sanitized in ignore_tags:
            return []

    isort_info = target[PyIsortInfo]
    srcs = isort_info.srcs.to_list()
    if not srcs:
        return []

    venv_toolchain = py_venv_common.get_toolchain(ctx, cfg = "exec")

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner, target],
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._runner_main],
        dep_info = dep_info,
    )

    marker = ctx.actions.declare_file("{}.isort.ok".format(target.label.name))
    aspect_name = "{}.isort".format(target.label.name)

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._runner_main,
        name = aspect_name,
        runfiles = dep_info.runfiles,
        use_runfiles_in_entrypoint = False,
        force_runfiles = True,
    )

    isort_info = target[PyIsortInfo]

    args = ctx.actions.args()
    args.add("--settings-path", ctx.file._config)
    args.add("--marker", marker)
    args.add_all(isort_info.imports, format_each = "--import=%s")
    args.add_all(srcs, format_each = "--src=%s")
    args.add("--")
    args.add("--check-only")
    args.add("--diff")

    ctx.actions.run(
        mnemonic = "PyIsort",
        progress_message = "isort %{label}",
        executable = executable,
        inputs = depset([ctx.file._config] + srcs),
        tools = runfiles.files,
        outputs = [marker],
        arguments = [args],
        env = ctx.configuration.default_shell_env,
    )

    return [OutputGroupInfo(
        py_isort_checks = depset([marker]),
    )]

py_isort_aspect = aspect(
    implementation = _py_isort_aspect_impl,
    doc = "An aspect for running isort on targets with Python sources.",
    attrs = {
        "_config": attr.label(
            doc = "The config file (isortrc) containing isort settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/isort:config"),
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running isort.",
            cfg = "exec",
            default = Label("//python/isort/private:isort_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the isort runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/isort/private:isort_runner.py"),
        ),
    } | py_venv_common.create_venv_attrs(),
    required_providers = [PyInfo],
    requires = [py_isort_target_aspect],
)
