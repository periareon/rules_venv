"""Bazel rules for building c extensions."""

load("@bazel_skylib//lib:paths.bzl", "paths")
load("@rules_cc//cc:action_names.bzl", "ACTION_NAMES")
load("@rules_cc//cc:cc_library.bzl", "cc_library")
load("@rules_cc//cc:cc_shared_library.bzl", "cc_shared_library")
load("@rules_cc//cc:find_cc_toolchain.bzl", "CC_TOOLCHAIN_TYPE", "find_cc_toolchain", "use_cc_toolchain")
load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")
load("@rules_cc//cc/common:cc_shared_library_info.bzl", "CcSharedLibraryInfo")
load("//python:py_info.bzl", "PyInfo")

def _compilation_mode_transition_impl(settings, attr):
    output = dict(settings)
    if attr.compilation_mode in ["dbg", "fastbuild", "opt"]:
        output["//command_line_option:compilation_mode"] = attr.compilation_mode
    return output

_compilation_mode_transition = transition(
    implementation = _compilation_mode_transition_impl,
    inputs = ["//command_line_option:compilation_mode"],
    outputs = ["//command_line_option:compilation_mode"],
)

def _get_imports(ctx, imports):
    """Determine the import paths from a target's `imports` attribute.

    Args:
        ctx (ctx): The rule's context object.
        imports (list): A list of import paths.

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

    return depset(result)

def target_platform_has_any_constraint(ctx, constraints):
    """Check if target platform has any of a list of constraints.

    Args:
        ctx: rule context.
        constraints: label_list of constraints.

    Returns:
        True if target platform has at least one of the constraints.
    """
    for constraint in constraints:
        constraint_value = constraint[platform_common.ConstraintValueInfo]
        if ctx.target_platform_has_constraint(constraint_value):
            return True
    return False

def _linux_cpu(ctx):
    if target_platform_has_any_constraint(ctx, [ctx.attr._cpu_aarch64]):
        return "aarch64"

    if target_platform_has_any_constraint(ctx, [ctx.attr._cpu_armv7]):
        return "arm"

    return "x86_64"

def _extension_name(*, name, linux_cpu, linux_abi, extension, py_toolchain):
    is_windows = extension.basename.endswith(".dll")
    is_macos = extension.basename.endswith(".dylib")

    py_runtime = py_toolchain.py3_runtime
    pyc_tag = py_runtime.pyc_tag
    extension = "so"

    if is_windows:
        extension = "pyd"
        platform = "win_amd64"
        pyc_tag = "cp{major}{minor}".format(
            major = py_runtime.interpreter_version_info.major,
            minor = py_runtime.interpreter_version_info.minor,
        )
    elif is_macos:
        platform = "darwin"
    else:
        platform = "{cpu}-linux-{abi}".format(
            cpu = linux_cpu,
            abi = linux_abi,
        ).rstrip("-")

    extension_template = "{module}.{pyc_tag}-{platform}.{ext}"
    extension_name = extension_template.format(
        module = name,
        pyc_tag = pyc_tag,
        platform = platform,
        ext = extension,
    )

    return extension_name

def _strip(ctx, input, output):
    """Strip `input` into `output` with the C++ toolchain's strip action.

    Args:
        ctx (ctx): The rule's context object.
        input (File): The shared library to strip.
        output (File): The stripped shared library.
    """
    cc_toolchain = find_cc_toolchain(ctx)
    feature_configuration = cc_common.configure_features(
        ctx = ctx,
        cc_toolchain = cc_toolchain,
        requested_features = ctx.features,
        unsupported_features = ctx.disabled_features,
    )
    if cc_common.is_enabled(feature_configuration = feature_configuration, feature_name = "no_stripping"):
        ctx.actions.symlink(output = output, target_file = input)
        return

    # The toolchain's strip command line and `--stripopt` are private to
    # Bazel's builtin rules, so the arguments are spelled out here.
    ctx.actions.run(
        mnemonic = "CcStrip",
        progress_message = "CcStrip %{label}",
        executable = cc_common.get_tool_for_action(
            feature_configuration = feature_configuration,
            action_name = ACTION_NAMES.strip,
        ),
        arguments = ["-S", "-o", output.path, input.path],
        inputs = depset([input], transitive = [cc_toolchain.all_files]),
        outputs = [output],
        toolchain = CC_TOOLCHAIN_TYPE,
    )

def _py_cc_extension_library_impl(ctx):
    extension = ctx.file.extension

    py_toolchain = ctx.toolchains["//python:toolchain_type"]
    ext = ctx.actions.declare_file(_extension_name(
        linux_cpu = _linux_cpu(ctx),
        linux_abi = ctx.attr.abi,
        name = ctx.label.name,
        extension = extension,
        py_toolchain = py_toolchain,
    ))

    if ctx.attr.stripped:
        _strip(ctx, extension, ext)
    else:
        ctx.actions.symlink(
            output = ext,
            target_file = extension,
        )

    providers = [
        DefaultInfo(
            files = depset([ext]),
            # `cc_shared_library` only forwards runfiles from `dynamic_deps`, so
            # the `data` of `library` and its `deps` has to come from `library`.
            runfiles = ctx.runfiles(files = [ext]).merge_all([
                ctx.attr.extension[DefaultInfo].default_runfiles,
                ctx.attr.library[DefaultInfo].default_runfiles,
            ]),
        ),
        PyInfo(
            imports = _get_imports(ctx, ctx.attr.imports),
            transitive_sources = depset(),
        ),
        coverage_common.instrumented_files_info(
            ctx,
            dependency_attributes = ["extension"],
        ),
    ]

    # Forward any aspect-generated outputs
    if OutputGroupInfo in ctx.attr.extension:
        providers.append(ctx.attr.extension[OutputGroupInfo])

    return providers

py_cc_extension_library = rule(
    doc = "Define a Python library for a module extension.",
    implementation = _py_cc_extension_library_impl,
    cfg = _compilation_mode_transition,
    attrs = {
        "abi": attr.string(
            doc = "An optional abi value for the output library name.",
        ),
        "compilation_mode": attr.string(
            doc = (
                "Specify the mode `extension` will be built in. For details see " +
                " [`--compilation_mode`](https://bazel.build/reference/command-line-reference#flag--compilation_mode)"
            ),
            values = [
                "dbg",
                "fastbuild",
                "opt",
                "current",
            ],
            default = "opt",
        ),
        "extension": attr.label(
            doc = "The module extension shared library.",
            cfg = "target",
            providers = [CcSharedLibraryInfo],
            allow_single_file = True,
            mandatory = True,
        ),
        "imports": attr.string_list(
            doc = "List of import directories to be added to the `PYTHONPATH`.",
        ),
        "library": attr.label(
            doc = "The `cc_library` linked into `extension`.",
            cfg = "target",
            providers = [CcInfo],
            mandatory = True,
        ),
        "stripped": attr.bool(
            doc = "Strip the shared library from `extension`.",
            default = False,
        ),
        "_cpu_aarch64": attr.label(
            default = Label("@platforms//cpu:aarch64"),
        ),
        "_cpu_armv7": attr.label(
            default = Label("@platforms//cpu:armv7"),
        ),
    },
    fragments = ["cpp"],
    toolchains = ["//python:toolchain_type"] + use_cc_toolchain(),
)

def _py_cc_extension_libs_impl(ctx):
    cc_info = ctx.attr.libs[CcInfo]

    libraries = []
    user_link_flags = []
    additional_inputs = []
    for linker_input in cc_info.linking_context.linker_inputs.to_list():
        libraries.extend(linker_input.libraries)
        user_link_flags.extend(linker_input.user_link_flags)
        additional_inputs.extend(linker_input.additional_inputs)

    linking_context = cc_common.create_linking_context(
        linker_inputs = depset([cc_common.create_linker_input(
            owner = ctx.label,
            libraries = depset(libraries),
            user_link_flags = user_link_flags,
            additional_inputs = depset(additional_inputs),
        )]),
    )

    return [
        DefaultInfo(
            files = ctx.attr.libs[DefaultInfo].files,
            runfiles = ctx.attr.libs[DefaultInfo].default_runfiles,
        ),
        CcInfo(
            compilation_context = cc_info.compilation_context,
            linking_context = linking_context,
        ),
    ]

py_cc_extension_libs = rule(
    doc = """\
Re-own the interpreter's link libraries so a `cc_shared_library` links them.

`cc_shared_library` only links inputs whose owner is a node of its `deps`
graph. `current_py_cc_libs` forwards a `CcInfo` straight from the toolchain,
so its linker inputs are owned by a target the graph never visits and are
silently dropped. On Windows that drops `python3X.lib`, which `pyconfig.h`
asks for with a `#pragma comment(lib)`, and the link fails.
""",
    implementation = _py_cc_extension_libs_impl,
    attrs = {
        "libs": attr.label(
            doc = "The interpreter's link libraries, e.g. `@rules_python//python/cc:current_py_cc_libs`.",
            providers = [CcInfo],
            mandatory = True,
        ),
    },
    # `cc_shared_library` builds its graph with an aspect that only visits
    # rules advertising `CcInfo`.
    provides = [CcInfo],
)

_LINUX_ABI = select({
    "@platforms//os:linux": "gnu",
    "//conditions:default": "",
})

def py_cc_extension(
        *,
        name,
        srcs,
        conlyopts = [],
        copts = [],
        cxxopts = [],
        data = [],
        defines = [],
        deps = [],
        dynamic_deps = [],
        imports = [],
        includes = [],
        linkopts = [],
        local_defines = None,
        compilation_mode = "opt",
        abi = _LINUX_ABI,
        stripped = None,
        **kwargs):
    """Define a Python C extension module.

    This target is consumed just as a `py_library` would be.

    The module is built as a `cc_shared_library`, so it provides
    `CcSharedLibraryInfo` and participates in rules_cc's checks that a static
    library is linked into only one shared library of a program.

    Args:
        name (str): The name of the target.
        srcs (list): he list of C and C++ files that are processed to create the library target. These
            are C/C++ source and header files, either non-generated (normal source code) or generated.
            For more details see [cc_library.srcs](https://bazel.build/reference/be/c-cpp#cc_library.srcs)
        conlyopts (list, optional): Add these options to the C compilation command.
            For more details see [cc_library.conlyopts](https://bazel.build/reference/be/c-cpp#cc_library.conlyopts)
        copts (list, optional): Add these options to the C/C++ compilation command.
            For more details see [cc_library.copts](https://bazel.build/reference/be/c-cpp#cc_library.copts)
        cxxopts (list, optional): Add these options to the C++ compilation command.
            For more details see [cc_library.cxxopts](https://bazel.build/reference/be/c-cpp#cc_library.cxxopts)
        data (list, optional): List of files used by this rule at compile time and runtime.
            For more details see [cc_library.data](https://bazel.build/reference/be/c-cpp#cc_library.data)
        defines (list, optional): List of defines to add to the compile line of this and all dependent targets
            For more details see [cc_library.defines](https://bazel.build/reference/be/c-cpp#cc_library.defines)
        deps (list, optional): The list of other libraries to be linked in to the extension.
            For more details see [cc_library.deps](https://bazel.build/reference/be/c-cpp#cc_library.deps)
        dynamic_deps (list, optional): These are other cc_shared_library dependencies the current target depends on.
            For more details see [cc_shared_library.dynamic_deps](https://bazel.build/reference/be/c-cpp#cc_shared_library.dynamic_deps)
        imports (list, optional): List of import directories to be added to the `PYTHONPATH`.
            For more details see [py_library.imports](https://bazel.build/reference/be/python#py_binary.imports).
        includes (list, optional): List of include dirs to be added to the compile line.
            For more details see [cc_library.includes](https://bazel.build/reference/be/c-cpp#cc_library.includes)
        linkopts (list, optional): Add these flags to the C++ linker command.
            For more details see [cc_shared_library.user_link_flags](https://bazel.build/reference/be/c-cpp#cc_shared_library.user_link_flags)
        local_defines (list, optional): List of defines to add to the compile line.
            For more details see [cc_library.local_defines](https://bazel.build/reference/be/c-cpp#cc_library.local_defines)
        compilation_mode (str, optional): The [compilation_mode](https://bazel.build/reference/command-line-reference#flag--compilation_mode)
            value to build the extension for. If set to `"current"`, the current configuration will be used.
        abi (str, optional): The ABI value to use for the output library name.
        stripped (bool, optional): Strip the shared library.
        **kwargs (dict): Additional keyword arguments for common definition attributes.
    """
    tags = kwargs.pop("tags", [])
    visibility = kwargs.pop("visibility", None)
    private_tags = depset(tags + ["manual"]).to_list()

    cc_library(
        name = name + "_lib",
        conlyopts = conlyopts,
        copts = copts,
        cxxopts = cxxopts,
        data = data,
        defines = defines,
        deps = [
            Label("@rules_python//python/cc:current_py_cc_headers"),
            # Not `@rules_python//python/cc:current_py_cc_libs` itself, see
            # `py_cc_extension_libs`.
            Label("//python/module_extension/private:current_py_cc_libs"),
        ] + deps,
        includes = includes,
        local_defines = local_defines,
        srcs = srcs,
        tags = private_tags,
        visibility = ["//visibility:private"],
        **kwargs
    )

    cc_shared_library(
        name = name + "_shared",
        deps = [name + "_lib"],
        dynamic_deps = dynamic_deps,
        user_link_flags = linkopts,
        tags = private_tags,
        visibility = ["//visibility:private"],
        **kwargs
    )

    py_cc_extension_library(
        name = name,
        extension = name + "_shared",
        library = name + "_lib",
        abi = abi,
        compilation_mode = compilation_mode,
        imports = imports,
        stripped = stripped,
        tags = tags,
        visibility = visibility,
        **kwargs
    )
