"""Bazel rules for ruff"""

load("@bazel_skylib//rules:common_settings.bzl", "BuildSettingInfo")
load("//python:py_info.bzl", "PyInfo")
load("//python/private:target_srcs.bzl", "find_srcs", "target_sources_aspect")
load("//python/venv:defs.bzl", "py_venv_common")
load(":ruff_toolchain.bzl", "TOOLCHAIN_TYPE", "rlocationpath")

_PY_SUFFIXES = [".py", ".pyi"]

def _is_valid_python_module_name(name):
    if not name:
        return False
    first = name[0]
    if not (first.isalpha() or first == "_"):
        return False
    for c in name.elems():
        if not (c.isalnum() or c == "_"):
            return False
    return True

def _first_party_module_from_file(file):
    """Return the top-level workspace module name for a Python source File, or None to skip it."""
    short_path = file.short_path
    if short_path.startswith("../"):
        return None

    seg, sep, _ = short_path.partition("/")
    if not seg:
        return None

    if not sep:
        # Workspace-root file: only .py / .pyi count as a module.
        stripped = False
        for suffix in _PY_SUFFIXES:
            if seg.endswith(suffix):
                seg = seg[:-len(suffix)]
                stripped = True
                break
        if not stripped:
            return None

    if not _is_valid_python_module_name(seg):
        return None
    return seg

def _add_first_party_module_args(args, pyinfo):
    """Emit `--first-party-module=<name>` for every top-level module in `pyinfo.transitive_sources`."""
    args.add_all(
        pyinfo.transitive_sources,
        map_each = _first_party_module_from_file,
        uniquify = True,
        format_each = "--first-party-module=%s",
    )

def _py_ruff_test_impl_common(ctx, mode):
    venv_toolchain = ctx.toolchains[py_venv_common.TOOLCHAIN_TYPE]

    # The runner has no runtime dependency on the target — it just shells
    # out to ruff. Only stage the runner's own deps in the venv, and add
    # the target's direct source files (the .py files being linted) as
    # runfiles so `--src <rlocation>` resolves inside the sandbox.
    runner_dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner],
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._runner_main],
        dep_info = runner_dep_info,
    )

    srcs = find_srcs(ctx.attr.target)
    srcs_runfiles = ctx.runfiles(transitive_files = srcs)

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._runner_main,
        runfiles = runner_dep_info.runfiles.merge(srcs_runfiles),
    )

    args = ctx.actions.args()
    args.set_param_file_format("multiline")
    args.add("--mode", mode)
    args.add("--config", rlocationpath(ctx.file.config, ctx.workspace_name))
    for src in srcs.to_list():
        args.add("--src", rlocationpath(src, ctx.workspace_name))
    _add_first_party_module_args(args, ctx.attr.target[PyInfo])

    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]
    if toolchain.ruff_bin:
        args.add("--ruff", rlocationpath(toolchain.ruff_bin))

    args_file = ctx.actions.declare_file("{}.ruff_args.txt".format(ctx.label.name))
    ctx.actions.write(
        output = args_file,
        content = args,
    )

    return [
        DefaultInfo(
            files = depset([executable]),
            runfiles = runfiles.merge(
                ctx.runfiles(files = [ctx.file.config, args_file], transitive_files = toolchain.all_files),
            ),
            executable = executable,
        ),
        RunEnvironmentInfo(
            environment = {
                "RULES_VENV_RUFF_RUNNER_ARGS_FILE": rlocationpath(args_file, ctx.workspace_name),
            },
        ),
    ]

_TEST_ATTRS = {
    "config": attr.label(
        doc = "The config file (ruff.toml) containing ruff settings.",
        cfg = "target",
        allow_single_file = True,
        default = Label("//python/ruff:config"),
    ),
    "target": attr.label(
        doc = "The target to run `ruff` on.",
        providers = [PyInfo],
        mandatory = True,
        aspects = [target_sources_aspect],
    ),
    "_runner": attr.label(
        doc = "The process wrapper for running ruff.",
        cfg = "exec",
        default = Label("//python/ruff/private:ruff_runner"),
    ),
    "_runner_main": attr.label(
        doc = "The main entrypoint for the ruff runner.",
        cfg = "exec",
        allow_single_file = True,
        default = Label("//python/ruff/private:ruff_runner.py"),
    ),
}

def _py_ruff_check_test_impl(ctx):
    return _py_ruff_test_impl_common(ctx, "check")

py_ruff_check_test = rule(
    implementation = _py_ruff_check_test_impl,
    doc = "A rule for running `ruff check` on a Python target.",
    attrs = _TEST_ATTRS,
    toolchains = [
        TOOLCHAIN_TYPE,
        py_venv_common.TOOLCHAIN_TYPE,
    ],
    test = True,
)

def _py_ruff_format_test_impl(ctx):
    return _py_ruff_test_impl_common(ctx, "format")

py_ruff_format_test = rule(
    implementation = _py_ruff_format_test_impl,
    doc = "A rule for running `ruff format` on a Python target.",
    attrs = _TEST_ATTRS,
    toolchains = [
        TOOLCHAIN_TYPE,
        py_venv_common.TOOLCHAIN_TYPE,
    ],
    test = True,
)

_IGNORE_TAGS = [
    "no_ruff",
    "noruff",
]

_MODE_IGNORE_TAGS = {
    "check": [
        "no_lint",
        "nolint",
        "no_ruff_lint",
        "no_ruff_check",
    ],
    "format": [
        "no_fmt",
        "no_format",
        "nofmt",
        "noformat",
        "no_ruff_format",
        "no_ruff_fmt",
    ],
}

def _py_ruff_aspect_impl(target, ctx):
    for tag in ctx.rule.attr.tags:
        sanitized = tag.replace("-", "_").lower()
        if sanitized in _IGNORE_TAGS:
            return []

    srcs = find_srcs(target, ctx)
    if not srcs:
        return []

    venv_toolchain = py_venv_common.get_toolchain(ctx, cfg = "exec")

    # Only the runner's own deps go into the venv. The target's Python
    # closure is NOT staged — ruff parses source text via `--src` and gets
    # first-party classification via analysis-time `--first-party-module`
    # args. That drops the aspect action's inputs from the target's entire
    # transitive pip closure down to a small constant (runner + config +
    # linted files + ruff binary).
    runner_dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner],
    )

    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._runner_main],
        dep_info = runner_dep_info,
    )

    aspect_name = "{}.ruff".format(target.label.name)

    executable, runfiles = py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._runner_main,
        name = aspect_name,
        runfiles = runner_dep_info.runfiles,
        use_runfiles_in_entrypoint = False,
        force_runfiles = True,
    )

    args = ctx.actions.args()
    args.add("--config", ctx.file._config)
    args.add_all(srcs, format_each = "--src=%s")
    _add_first_party_module_args(args, target[PyInfo])

    toolchain = ctx.toolchains[TOOLCHAIN_TYPE]
    if toolchain.ruff_bin:
        args.add("--ruff", toolchain.ruff_bin)

    markers = []

    modes = ctx.attr._modes[BuildSettingInfo].value
    for mode in modes:
        # Handle granular tag skipping per mode.
        ignore_tags = _MODE_IGNORE_TAGS[mode]
        skip = False
        for tag in ctx.rule.attr.tags:
            sanitized = tag.replace("-", "_").lower()
            if sanitized in ignore_tags:
                skip = True
                break

        if skip:
            continue

        marker = ctx.actions.declare_file("{}.ruff.{}.ok".format(target.label.name, mode))
        markers.append(marker)

        mode_args = ctx.actions.args()
        mode_args.add("--mode", mode)
        mode_args.add("--marker", marker)

        ctx.actions.run(
            mnemonic = "PyRuff{}".format(mode.capitalize()),
            progress_message = "PyRuff ({}) %{{label}}".format(mode.capitalize()),
            executable = executable,
            inputs = depset([ctx.file._config], transitive = [srcs]),
            tools = depset(transitive = [runfiles.files, toolchain.all_files]),
            outputs = [marker],
            arguments = [mode_args, args],
            env = ctx.configuration.default_shell_env,
        )

    if not markers:
        return []

    return [OutputGroupInfo(
        py_ruff_checks = depset(markers),
    )]

py_ruff_aspect = aspect(
    implementation = _py_ruff_aspect_impl,
    doc = """\
An aspect for running ruff on targets with Python sources.

This aspect can be configured by adding the following snippet to a workspace's `.bazelrc` file:

```text
build --aspects=@rules_venv//python/ruff:py_ruff_aspect.bzl%py_ruff_aspect
build --output_groups=+py_ruff_checks
```
""",
    attrs = {
        "_config": attr.label(
            doc = "The config file (ruff.toml) containing ruff settings.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/ruff:config"),
        ),
        "_modes": attr.label(
            doc = "The type of check ruff should perform.",
            default = Label("//python/ruff:mode"),
        ),
        "_runner": attr.label(
            doc = "The process wrapper for running ruff.",
            cfg = "exec",
            default = Label("//python/ruff/private:ruff_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the ruff runner.",
            cfg = "exec",
            allow_single_file = True,
            default = Label("//python/ruff/private:ruff_runner.py"),
        ),
    } | py_venv_common.create_venv_attrs(),
    toolchains = [TOOLCHAIN_TYPE],
    required_providers = [PyInfo],
    requires = [
        target_sources_aspect,
    ],
)
