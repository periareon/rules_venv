"""pex toolchain rules."""

TOOLCHAIN_TYPE = str(Label("//python/pex:toolchain_type"))

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _py_pex_toolchain_impl(ctx):
    platform = None
    if ctx.attr.platform:
        platform = ctx.attr.platform

    # Generate scie download directory (contains safe-cache structure)
    scie_cache_dir = ctx.actions.declare_directory(ctx.label.name + ".scie_cache")

    cache_args = ctx.actions.args()
    cache_args.add("--output_dir", scie_cache_dir.path)
    cache_args.add("--science", ctx.file.scie_science)
    cache_args.add("--jump", ctx.file.scie_jump)
    cache_args.add("--ptex", ctx.file.scie_ptex)
    cache_args.add("--interpreter", ctx.file.scie_python_interpreter)
    cache_args.add("--interpreter_version", ctx.attr.scie_python_version)

    # Generate the cache directory and verify it with science download
    ctx.actions.run(
        mnemonic = "PyPexScieCacheDir",
        executable = ctx.executable._cache_generator,
        arguments = [cache_args],
        inputs = [
            ctx.file.scie_science,
            ctx.file.scie_jump,
            ctx.file.scie_ptex,
            ctx.file.scie_python_interpreter,
        ],
        outputs = [scie_cache_dir],
        tools = [ctx.executable._cache_generator, ctx.file.scie_science],
    )

    all_files = depset([
        ctx.file.pex,
        ctx.file.scie_science,
        ctx.file.scie_jump,
        ctx.file.scie_ptex,
        ctx.file.scie_python_interpreter,
        scie_cache_dir,
    ])

    make_variable_info = platform_common.TemplateVariableInfo({
        "PEX": ctx.file.pex.path,
        "PEX_RLOCATIONPATH": _rlocationpath(ctx.file.pex, ctx.workspace_name),
        "SCIE_JUMP": ctx.file.scie_jump.path,
        "SCIE_JUMP_RLOCATIONPATH": _rlocationpath(ctx.file.scie_jump, ctx.workspace_name),
        "SCIE_PTEX": ctx.file.scie_ptex.path,
        "SCIE_PTEX_RLOCATIONPATH": _rlocationpath(ctx.file.scie_ptex, ctx.workspace_name),
        "SCIE_SCIENCE": ctx.file.scie_science.path,
        "SCIE_SCIENCE_RLOCATIONPATH": _rlocationpath(ctx.file.scie_science, ctx.workspace_name),
    })

    return [
        platform_common.ToolchainInfo(
            make_variables = make_variable_info,
            pex = ctx.file.pex,
            platform = platform,
            scie_cache_dir = scie_cache_dir,
            scie_jump = ctx.file.scie_jump,
            scie_ptex = ctx.file.scie_ptex,
            scie_python_interpreter = ctx.file.scie_python_interpreter,
            scie_python_version = ctx.attr.scie_python_version,
            scie_science = ctx.file.scie_science,
            all_files = all_files,
        ),
        make_variable_info,
    ]

py_pex_toolchain = rule(
    implementation = _py_pex_toolchain_impl,
    doc = "A toolchain for the [pex](https://github.com/pantsbuild/pex) packaging tool rules.",
    attrs = {
        "pex": attr.label(
            doc = "The pex binary to use with the rules.",
            allow_single_file = True,
            executable = True,
            cfg = "exec",
            mandatory = True,
        ),
        "platform": attr.string(
            doc = "The platform to target for scie executables.",
            mandatory = True,
        ),
        "scie_jump": attr.label(
            doc = "The scie jump binary to use for scie targets.",
            allow_single_file = True,
            executable = True,
            cfg = "exec",
            mandatory = True,
        ),
        "scie_ptex": attr.label(
            doc = "The scie ptex binary to use for scie targets.",
            allow_single_file = True,
            executable = True,
            cfg = "exec",
            mandatory = True,
        ),
        "scie_python_interpreter": attr.label(
            doc = "The standalone python interpreter archive (.tar.gz) to bundle into scie binaries.",
            allow_single_file = True,
            cfg = "target",
            mandatory = True,
        ),
        "scie_python_version": attr.string(
            doc = "The Python version string to pass to pex for scie builds (e.g., '3.11').",
            mandatory = True,
        ),
        "scie_science": attr.label(
            doc = "The scie science binary to use for scie targets.",
            allow_single_file = True,
            executable = True,
            cfg = "exec",
            mandatory = True,
        ),
        "_cache_generator": attr.label(
            default = Label("//python/pex/private:scie_cache_generator"),
            executable = True,
            cfg = "exec",
        ),
    },
)

def _current_py_pex_toolchain_impl(ctx):
    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]

    # Create DefaultInfo with toolchain files
    default_info = DefaultInfo(
        files = depset([toolchain.pex]),
        runfiles = ctx.runfiles(transitive_files = toolchain.all_files),
    )

    return [
        toolchain,
        toolchain.make_variables,
        default_info,
    ]

current_py_pex_toolchain = rule(
    doc = "A rule for exposing the current registered `py_pex_toolchain`.",
    implementation = _current_py_pex_toolchain_impl,
    toolchains = [TOOLCHAIN_TYPE],
)
