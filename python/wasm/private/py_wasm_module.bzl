"""The `py_wasm_module` rule."""

load("//python:py_info.bzl", "PyInfo")
load("//python/wasm:py_wasm_toolchain.bzl", "TOOLCHAIN_TYPE")

# rules_python's toolchains, both resolved by the same `is_python_X.Y` as the
# `py_wasm_toolchain`: the C toolchain, for the headers of the Python of the
# target configuration, and the exec tools toolchain, for an interpreter built
# for the execution platform, which runs the build tools.
_PY_CC_TOOLCHAIN_TYPE = str(Label("@rules_python//python/cc:toolchain_type"))
_PY_EXEC_TOOLS_TOOLCHAIN_TYPE = str(Label("@rules_python//python:exec_tools_toolchain_type"))
_PYTHON_VERSION_FLAG = str(Label("@rules_python//python/config_settings:python_version"))

def _python_version_transition_impl(settings, attr):
    """Build for `python_version`: it selects the Python toolchain, and with it the CPython embedded."""
    if not attr.python_version:
        return {_PYTHON_VERSION_FLAG: settings[_PYTHON_VERSION_FLAG]}
    return {_PYTHON_VERSION_FLAG: attr.python_version}

_python_version_transition = transition(
    implementation = _python_version_transition_impl,
    inputs = [_PYTHON_VERSION_FLAG],
    outputs = [_PYTHON_VERSION_FLAG],
)

def _is_identifier(name):
    """Whether `name` can name a Python function."""
    if not name or name[0].isdigit():
        return False
    for char in name.elems():
        if not (char.isalnum() or char == "_"):
            return False
    return True

def _runfiles_path(ctx, file):
    """The path of a source under the runfiles root, `<repository>/<path>`."""
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]
    return "{}/{}".format(ctx.workspace_name, file.short_path)

def _bundle_names(ctx, deps):
    """Map every transitive source to the names it is importable under.

    A venv puts each import root on `sys.path`: the root of every repository
    a dependency comes from, and the `imports` of the libraries. A source is
    bundled under its path relative to each root that contains it, which is
    the name an `import` statement resolves to.
    """
    roots = {}
    sources = []
    for dep in deps:
        info = dep[PyInfo]
        workspace_name = dep.label.workspace_name or ctx.workspace_name
        roots[workspace_name] = None
        for root in info.imports.to_list():
            roots[root] = None
        sources.append(info.transitive_sources)

    names = []
    files = depset(transitive = sources).to_list()
    for file in files:
        path = _runfiles_path(ctx, file)
        for root in roots:
            if path.startswith(root + "/"):
                names.append((path[len(root) + 1:], file))
    return names, files

def _check_version(ctx, toolchain, what, version):
    """Fail unless `version` (a `struct` like `sys.version_info`) is the toolchain's CPython, final."""
    actual = "{}.{}".format(version.major, version.minor)
    if actual != toolchain.python_version:
        fail(
            "py_wasm_module {}: {} is Python {} but the `py_wasm_toolchain` embeds CPython {}. ".format(ctx.label, what, actual, toolchain.python_version) +
            "The two must agree: the toolchain's headers compile the module and its interpreter produces " +
            "the module's bytecode. Set `python_version` to a version that has a `py_wasm_toolchain`.",
        )
    releaselevel = getattr(version, "releaselevel", "final")
    if releaselevel != "final":
        fail(
            "py_wasm_module {}: {} is a pre-release, {}.{}.{}{}, but the `py_wasm_toolchain` ".format(ctx.label, what, version.major, version.minor, version.micro, releaselevel) +
            "embeds a final CPython {}. A pre-release's bytecode and C ABI may differ from the release's, ".format(toolchain.python_version) +
            "which would fail at pre-initialization or at a call; register a final release of Python {}.".format(toolchain.python_version),
        )

def _exec_interpreter(ctx, toolchain):
    """The interpreter that runs the build tools, checked against the toolchain.

    The tools marshal bytecode and freeze modules for the interpreter in the
    module, which only an interpreter of the same `X.Y` can do. rules_python's
    exec tools toolchain provides one built for the execution platform, as a
    tool run in an action must be, and is eligible by the same `is_python_X.Y`
    as the `py_wasm_toolchain`, which pairs the two.
    """
    exec_tools = getattr(ctx.toolchains[_PY_EXEC_TOOLS_TOOLCHAIN_TYPE], "exec_tools", None)
    interpreter = getattr(exec_tools, "exec_interpreter", None)
    if interpreter == None:
        fail(
            "py_wasm_module {} needs an interpreter to run its build tools, but rules_python's exec tools ".format(ctx.label) +
            "toolchain provides none (`exec_interpreter`); see `--@rules_python//python/config_settings:exec_tools_toolchain`.",
        )
    runtime = getattr(interpreter[platform_common.ToolchainInfo], "py3_runtime", None) if platform_common.ToolchainInfo in interpreter else None
    version = getattr(runtime, "interpreter_version_info", None)
    if version != None:
        _check_version(ctx, toolchain, "the exec tools toolchain's interpreter", version)
    return interpreter[DefaultInfo].files_to_run

def _run_python(ctx, interpreter, *, mnemonic, script, arguments, inputs, outputs, progress_message):
    """Run one of the build tools with the exec interpreter."""
    args = ctx.actions.args()

    # No bytecode beside the script, no `site`, no user site.
    args.add_all(["-B", "-S", "-s", script])
    ctx.actions.run(
        mnemonic = mnemonic,
        executable = interpreter,
        arguments = [args] + arguments,
        inputs = depset([script], transitive = [inputs]),
        outputs = outputs,
        env = {
            # Marshalled frozensets follow string hashes; fix them so that the
            # bytecode is reproducible.
            "PYTHONHASHSEED": "0",
            # Keep the script's directory off `sys.path`.
            "PYTHONSAFEPATH": "1",
        },
        progress_message = progress_message,
        toolchain = _PY_EXEC_TOOLS_TOOLCHAIN_TYPE,
    )

def _py_wasm_module_impl(ctx):
    if not ctx.attr.exports:
        fail("`exports` must name at least one function of the entry module")
    for name in ctx.attr.exports:
        if not _is_identifier(name):
            fail("`exports` of {} names `{}`, which is not a Python identifier".format(ctx.label, name))

    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]
    interpreter = _exec_interpreter(ctx, toolchain)
    if ctx.attr.preinitialize and toolchain.wizer == None:
        fail(
            "`preinitialize` of {} needs Wizer, which the `py_wasm_toolchain` in use does not provide. ".format(ctx.label) +
            "Give the toolchain a `wizer`, or set `preinitialize = False` and accept that every call " +
            "starts the interpreter.",
        )
    clang = toolchain.clang
    wasi_sdk = toolchain.compiler_files
    name = ctx.label.name

    # 1. The bundle: the standard library and the sources of `deps`, served
    #    by the importer of bootstrap.py.
    bundle = ctx.actions.declare_file("{}.bundle".format(name))
    names, sources = _bundle_names(ctx, ctx.attr.deps)
    args = ctx.actions.args()
    args.add("--out", bundle)
    args.add("--stdlib", toolchain.stdlib_dir)
    args.add("--pyc")
    args.add("--expect-version", toolchain.python_version)
    for bundle_name, file in names:
        args.add("--file", "{}={}".format(bundle_name, file.path))
    args.use_param_file("@%s", use_always = True)
    args.set_param_file_format("multiline")
    _run_python(
        ctx,
        interpreter,
        mnemonic = "PyWasmBundle",
        script = ctx.file._bundle_py,
        arguments = [args],
        inputs = depset(sources, transitive = [toolchain.stdlib_files]),
        outputs = [bundle],
        progress_message = "Bundling Python sources for %{label}",
    )

    # 2. The `encodings` modules, frozen: the interpreter needs them before the
    #    bundle importer exists.
    frozen_c = ctx.actions.declare_file("{}.frozen_encodings.c".format(name))
    args = ctx.actions.args()
    args.add("--stdlib", toolchain.stdlib_dir)
    args.add("--out", frozen_c)
    args.add("--expect-version", toolchain.python_version)
    _run_python(
        ctx,
        interpreter,
        mnemonic = "PyWasmFreeze",
        script = ctx.file._freeze_encodings_py,
        arguments = [args],
        inputs = toolchain.stdlib_files,
        outputs = [frozen_c],
        progress_message = "Freezing encodings for %{label}",
    )

    # 3. The generated sources: the exports and the embedded data.
    exports_c = ctx.actions.declare_file("{}.exports.c".format(name))
    lines = [
        "/* Generated by py_wasm_module for {}. */".format(ctx.label),
        "#include <stdint.h>",
        "",
        "uint32_t rules_venv_py_wasm_call(const char *function, const uint8_t *input, uint32_t input_len, uint8_t **out_ptr, uint32_t *out_len);",
        "",
        "const char rules_venv_py_wasm_entry_module[] = \"{}\";".format(ctx.attr.entry),
    ]
    for index, export in enumerate(ctx.attr.exports):
        lines.extend([
            "",
            "__attribute__((export_name(\"{name}\"))) uint32_t rules_venv_py_wasm_export_{index}(const uint8_t *input, uint32_t input_len, uint8_t **out_ptr, uint32_t *out_len) {{".format(name = export, index = index),
            "    return rules_venv_py_wasm_call(\"{}\", input, input_len, out_ptr, out_len);".format(export),
            "}",
        ])
    ctx.actions.write(exports_c, "\n".join(lines) + "\n")

    embed_s = ctx.actions.declare_file("{}.embed.S".format(name))
    ctx.actions.write(embed_s, """\
# Generated by py_wasm_module: the bundle and the bootstrap as data.
    .section .rodata.bundle,"",@
    .globl rules_venv_py_wasm_bundle_start
    .type rules_venv_py_wasm_bundle_start,@object
    .p2align 4
rules_venv_py_wasm_bundle_start:
    .incbin "{bundle}"
    .size rules_venv_py_wasm_bundle_start, .-rules_venv_py_wasm_bundle_start
    .globl rules_venv_py_wasm_bundle_end
    .type rules_venv_py_wasm_bundle_end,@object
rules_venv_py_wasm_bundle_end:
    .byte 0
    .size rules_venv_py_wasm_bundle_end, 1

    .section .rodata.bootstrap,"",@
    .globl rules_venv_py_wasm_bootstrap_src
    .type rules_venv_py_wasm_bootstrap_src,@object
rules_venv_py_wasm_bootstrap_src:
    .incbin "{bootstrap}"
    .byte 0
    .size rules_venv_py_wasm_bootstrap_src, .-rules_venv_py_wasm_bootstrap_src
""".format(bundle = bundle.path, bootstrap = ctx.file._bootstrap.path))

    # 4. Compile the host pieces. The headers are the Python toolchain's, whose
    #    `pyconfig.h` describes the host; including the CPython build's first
    #    makes the toolchain's a no-op, since both share the include guard.
    py_cc_toolchain = ctx.toolchains[_PY_CC_TOOLCHAIN_TYPE].py_cc_toolchain
    if not py_cc_toolchain.python_version.startswith(toolchain.python_version + "."):
        fail(
            "py_wasm_module {}: the Python toolchain's headers are Python {} but the `py_wasm_toolchain` ".format(ctx.label, py_cc_toolchain.python_version) +
            "embeds CPython {}. Set `python_version` to a version that has a `py_wasm_toolchain`.".format(toolchain.python_version),
        )
    headers = py_cc_toolchain.headers.providers_map["CcInfo"].compilation_context
    include_flags = []
    for directory in headers.system_includes.to_list():
        include_flags.extend(["-isystem", directory])
    for directory in headers.includes.to_list():
        include_flags.extend(["-I", directory])
    for directory in headers.quote_includes.to_list():
        include_flags.extend(["-iquote", directory])
    common_flags = [
        "--target=wasm32-wasi",
        "--sysroot=" + toolchain.sysroot,
    ]
    objects = []
    compile_units = [
        (ctx.file._shim, []),
        (ctx.file._wasi_stubs, []),
        (exports_c, []),
        (frozen_c, []),
        (embed_s, [bundle, ctx.file._bootstrap]),
    ]
    for source, extra_inputs in compile_units:
        obj = ctx.actions.declare_file("{}.objs/{}.o".format(name, source.basename))
        args = ctx.actions.args()
        args.add_all(common_flags)
        args.add_all(["-O2", "-DNDEBUG"])
        if source.extension == "c":
            args.add("-include", toolchain.pyconfig)
            args.add_all(include_flags)
        args.add_all(["-c", source, "-o", obj])
        ctx.actions.run(
            mnemonic = "PyWasmCompile",
            executable = clang,
            arguments = [args],
            inputs = depset([source, toolchain.pyconfig] + extra_inputs, transitive = [wasi_sdk, headers.headers]),
            outputs = [obj],
            progress_message = "Compiling %{input} for %{label}",
            toolchain = TOOLCHAIN_TYPE,
        )
        objects.append(obj)

    # 5. Link a reactor module with no imports. No `-O` here: at link time it
    #    would merge functions into very large ones, which some runtimes
    #    cannot compile.
    linked = ctx.actions.declare_file("{}.linked.wasm".format(name)) if ctx.attr.preinitialize else ctx.actions.declare_file("{}.wasm".format(name))
    args = ctx.actions.args()
    args.add_all(common_flags)
    args.add("-mexec-model=reactor")
    if ctx.attr.strip:
        args.add("-Wl,--strip-all")
    args.add_all(["-o", linked])
    args.add_all(objects)
    args.add_all(toolchain.cpython_libs)
    args.add_all(toolchain.linkopts)
    args.add("-Wl,-z,stack-size={}".format(ctx.attr.stack_size))
    args.add("-Wl,--initial-memory={}".format(ctx.attr.initial_memory))
    ctx.actions.run(
        mnemonic = "PyWasmLink",
        executable = clang,
        arguments = [args],
        inputs = depset(objects + toolchain.cpython_libs, transitive = [wasi_sdk]),
        outputs = [linked],
        progress_message = "Linking %{output}",
        toolchain = TOOLCHAIN_TYPE,
    )

    output = linked
    if ctx.attr.preinitialize:
        # 6. Run the interpreter start-up and the imports now and snapshot the
        #    memory into the module; a call starts from there.
        snapshot = ctx.actions.declare_file("{}.wizer.wasm".format(name))
        ctx.actions.run(
            mnemonic = "PyWasmPreinitialize",
            executable = toolchain.wizer,
            arguments = [
                "--init-func",
                "wizer.initialize",
                "--wasm-bulk-memory",
                "true",
                "-o",
                snapshot.path,
                linked.path,
            ],
            inputs = [linked],
            outputs = [snapshot],
            progress_message = "Pre-initializing %{label}",
            toolchain = TOOLCHAIN_TYPE,
        )

        # Wizer leaves the original data segments as empty passive placeholders
        # and writes the snapshot as many small active ones; merge them.
        output = ctx.actions.declare_file("{}.wasm".format(name))
        args = ctx.actions.args()
        args.add_all([snapshot, output])
        _run_python(
            ctx,
            interpreter,
            mnemonic = "PyWasmMergeSegments",
            script = ctx.file._merge_segments_py,
            arguments = [args],
            inputs = depset([snapshot]),
            outputs = [output],
            progress_message = "Merging data segments of %{output}",
        )

    return [DefaultInfo(files = depset([output]))]

py_wasm_module = rule(
    doc = """\
Build a self-contained WebAssembly module embedding CPython and Python sources.

The output, `<name>.wasm`, imports nothing and exports `memory`, `allocate` and
one function per entry of `exports`; the module documentation of `defs.bzl`
gives the calling convention. Each export calls the function of the same name
in the `entry` module with the call's input as `bytes` and returns what it
returns: `bytes`, or `(bytes, code)` to set the return code. An exception
becomes return code 2 with the traceback in the output.

The module holds the sources of `deps` as a venv would import them, the
standard library as bytecode, and, by default, a snapshot of the interpreter
taken after the entry module was imported, so that a call does not pay for
start-up. The CPython is the one of `python_version`, which also selects the
rules_python toolchain the module is built with. See the module documentation
of `defs.bzl` and `py_wasm_toolchain`.
""",
    implementation = _py_wasm_module_impl,
    attrs = {
        "deps": attr.label_list(
            doc = "The Python libraries the entry module imports, bundled with their transitive dependencies.",
            providers = [PyInfo],
        ),
        "entry": attr.string(
            doc = "The dotted name of the module holding the exported functions, e.g. `my_rules.wasm.entry`.",
            mandatory = True,
        ),
        "exports": attr.string_list(
            doc = "The functions of `entry` to export, each under its own name.",
            mandatory = True,
        ),
        "initial_memory": attr.int(
            doc = "The initial size of the module's memory, in bytes. It grows as needed, up to any limit the runtime imposes.",
            default = 64 * 1024 * 1024,
        ),
        "preinitialize": attr.bool(
            doc = "Snapshot the interpreter after importing `entry` with Wizer, so a call starts from there. Without it every call starts the interpreter, which can take seconds under an interpreting runtime.",
            default = True,
        ),
        "python_version": attr.string(
            doc = "The Python version to build for, `X.Y`: the module embeds that CPython and is built with that rules_python toolchain, which must be registered. Unset, the build's current Python version, which must have a `py_wasm_toolchain`; see \"Toolchains\" in the module documentation of `defs.bzl`.",
        ),
        "stack_size": attr.int(
            doc = "The size of the C stack, in bytes.",
            default = 8 * 1024 * 1024,
        ),
        "strip": attr.bool(
            doc = "Strip the name section and other debug information from the module.",
            default = True,
        ),
        "_allowlist_function_transition": attr.label(
            default = Label("@bazel_tools//tools/allowlists/function_transition_allowlist"),
        ),
        "_bootstrap": attr.label(
            default = Label("//python/wasm/private:bootstrap.py"),
            allow_single_file = True,
        ),
        "_bundle_py": attr.label(
            default = Label("//python/wasm/private:bundle.py"),
            allow_single_file = True,
        ),
        "_freeze_encodings_py": attr.label(
            default = Label("//python/wasm/private:freeze_encodings.py"),
            allow_single_file = True,
        ),
        "_merge_segments_py": attr.label(
            default = Label("//python/wasm/private:merge_segments.py"),
            allow_single_file = True,
        ),
        "_shim": attr.label(
            default = Label("//python/wasm/private:shim.c"),
            allow_single_file = True,
        ),
        "_wasi_stubs": attr.label(
            default = Label("//python/wasm/private:wasi_stubs.c"),
            allow_single_file = True,
        ),
    },
    cfg = _python_version_transition,
    toolchains = [
        TOOLCHAIN_TYPE,
        _PY_CC_TOOLCHAIN_TYPE,
        _PY_EXEC_TOOLS_TOOLCHAIN_TYPE,
    ],
)
