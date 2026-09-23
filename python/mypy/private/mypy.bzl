"""Bazel rules for mypy"""

load("//python:py_info.bzl", "PyInfo")
load("//python/private:target_srcs.bzl", "find_srcs", "target_sources_aspect")
load("//python/venv:defs.bzl", "py_venv_common")
load(":mypy_toolchain.bzl", "TOOLCHAIN_TYPE")

PyMypyCacheInfo = provider(
    doc = """\
Mypy type information a consumer can use in place of a target's sources.

mypy only needs a dependency's *source* to recover its types when it has
no cache for it. Given one, an empty file at the right path is enough, so
a target that depends on hundreds of others can read a small cache per
dependency instead of the whole source closure. Each cache holds only
what its own action added -- the standard library and the shared parts
of the graph appear exactly once -- so consumers take the entire depset
rather than merging anything themselves.""",
    fields = {
        "caches": "depset[File]: The caches of this target and its transitive dependencies.",
        "covered": """\
depset[File]: The files those caches stand in for. A consumer drops
these from the venv it builds and from its action's inputs, which is
where the saving actually comes from: the cache is only worth shipping
if the sources it replaces stop being shipped.""",
    },
)

# Tags that opt a target out of being *checked*. Such targets still
# publish their types: a dependency that does not do so cannot be pruned
# from its consumers, which would put the whole source closure back.
_IGNORE_TAGS = [
    "no_mypy",
    "no_lint",
    "nolint",
    "nomypy",
]

_MYPY_SOURCE_EXTENSIONS = ["py", "pyi"]

# A cache travels along every attribute, because `deps` is not the only
# attribute that puts Python in the venv an action builds. An ordinary
# `py_library` is indeed reached through `deps` alone, but a rule is free
# to assemble its `PyInfo` from anywhere -- the rules here build theirs
# from the `_runner` holding a process wrapper, and `py_mypy_test` from
# its `target` -- and a library that arrives by such an edge is staged
# like any other. Enumerating the attributes instead would mean a list
# that has to know every rule in the build, including rules outside this
# repository, and a name missing from it fails silently: the sources come
# back with no cache to replace them and everything still passes.
_ATTR_ASPECTS = ["*"]

def _is_ignored(ctx):
    for tag in ctx.rule.attr.tags:
        if tag.replace("-", "_").lower() in _IGNORE_TAGS:
            return True
    return False

def _dep_caches(ctx):
    """Collect what a target's Python dependencies published.

    Every attribute is scanned, matching the edges the aspect propagates
    along. A cache that is not collected here is a dependency whose
    sources mypy finds and re-analyzes from scratch, and whose results
    this target then republishes.

    Returns:
        struct: `caches` and `covered`, the depsets this target inherits,
        and `py_deps`, whether any attribute named a Python target at
        all.
    """
    caches = []
    covered = []
    py_deps = False

    for name in dir(ctx.rule.attr):
        value = getattr(ctx.rule.attr, name)

        # Label lists and dicts are as common as plain labels, and a dict
        # can be keyed either way round, so both halves are looked at.
        if type(value) == "list":
            deps = value
        elif type(value) == "dict":
            deps = value.keys() + value.values()
        elif type(value) == "Target":
            deps = [value]
        else:
            # Most attributes are strings, ints and bools. Skipping them
            # here avoids a throwaway list per attribute per target.
            continue

        for dep in deps:
            if type(dep) != "Target":
                continue
            if PyInfo in dep:
                py_deps = True
            if PyMypyCacheInfo in dep:
                caches.append(dep[PyMypyCacheInfo].caches)
                covered.append(dep[PyMypyCacheInfo].covered)

    return struct(
        caches = depset(transitive = caches),
        covered = depset(transitive = covered),
        py_deps = py_deps,
    )

def _module_key(file):
    """What a `.py` and the `.pyi` describing it have in common.

    A stub and the module it describes are one module as far as mypy is
    concerned, and it refuses to be handed both, so the two have to be
    recognized as a pair wherever either is chosen over the other.

    Keyed on the short path: a generated stub sits under `bazel-out`
    while the module it shadows is in the source tree, so their exec
    paths never match.
    """
    return file.short_path[:-len(file.extension)]

def _pick_modules(files):
    """One file per module, from an arbitrary pile of files.

    Anything that is not Python is dropped, and a module that has a stub
    is represented by the stub, which is the one that decides the types
    and the one mypy uses. It refuses to be handed both.
    """
    by_module = {}
    for file in files:
        if file.extension not in _MYPY_SOURCE_EXTENSIONS:
            continue

        key = _module_key(file)
        seen = by_module.get(key)
        if seen and seen.extension == "pyi":
            continue
        by_module[key] = file

    return by_module.values()

def _staged_files(ctx):
    """Everything a target stages into the venv beside its sources.

    Wheels put `.py` in `srcs` and everything else -- stubs, PEP 561
    markers, data -- in `data`, so the two are always looked at together.
    """
    files = []
    for attr in ("srcs", "data"):
        files += getattr(ctx.rule.files, attr, [])

    return files

def _unchecked_srcs(ctx):
    """The Python files of a target that is cached but not checked.

    `find_srcs` hides external targets so third-party code is never
    linted, and drops generated files. Neither can be skipped here,
    because a consumer can only prune what something has cached.
    """
    return _pick_modules(_staged_files(ctx))

def _covered_files(ctx, analyzed):
    """Everything a consumer may leave out once it holds this cache.

    What was analyzed, plus the files staged beside it that mypy
    provably never opens: anything that is not Python at all -- which is
    where the PEP 561 markers are accounted for -- and a `.py` whose
    `.pyi` is the one that was analyzed.

    Sources this target does not analyze are deliberately not here. A
    generated `.py` is dropped by `find_srcs` and so never reaches the
    manifest, but mypy still reads it when something imports it, and
    pruning it would leave nothing in its place.
    """
    covered = {file: None for file in analyzed}
    stubbed = {
        _module_key(file): None
        for file in analyzed
        if file.extension == "pyi"
    }

    for file in _staged_files(ctx):
        if file.extension not in _MYPY_SOURCE_EXTENSIONS or _module_key(file) in stubbed:
            covered[file] = None

    return covered.keys()

def _prunable(ctx, covered, analyzed):
    """The files this action can leave out, keyed by execution path.

    A file is prunable when some cache among the action's inputs stands
    in for it, with two exceptions.

    The first is anything this action is itself going to analyze. A
    source can belong to two targets at once, and a dependency's cache
    covering it says only that the dependency read it, not that this
    action may stop reading it. Pruning it would replace the real file
    with the empty stand-in the runner writes, which mypy would then
    check and find nothing wrong with.

    The second is nothing mypy itself is made of. The runner's own
    closure is the program being executed, not a dependency being
    analyzed, and a target that happens to depend on `mypy` or
    `typing_extensions` would otherwise prune the interpreter's view of
    the tool out from under it. That incidentally covers the commonest
    way a cache comes back standing in for nothing -- mypy refuses to
    analyze a wheel that shadows a module it bundles, and every such
    package is by definition one mypy ships, so it is kept here anyway.
    Other ways of blocking mypy are not covered: a cache-only target that
    stages the same module twice publishes an empty cache all the same,
    and its consumers, already told here that its sources are covered,
    report the modules as missing. The runner says so on the way past.
    """
    files = covered.to_list()

    # A target whose inputs cover nothing prunes nothing, and that is most
    # of them. Answering before flattening the runner's closure keeps the
    # aspect from paying for it on every target in the build.
    if not files:
        return {}

    # The runner's runfiles already carry its transitive sources, so this
    # is the whole closure in one pass.
    keep = {
        file.path: None
        for file in ctx.attr._runner[DefaultInfo].default_runfiles.files.to_list()
    }
    for file in analyzed:
        keep[file.path] = None

    return {
        file.path: None
        for file in files
        if file.path not in keep
    }

def _prune_dep_info(ctx, dep_info, prunable):
    """Rebuild dependency info without the sources the caches replace.

    The import paths are left as they are, and pruning a root down to
    nothing is allowed to empty its directory. The venv creates every
    directory it names in a `.pth`, so a root stays on `sys.path` whether
    or not anything is left under it, and the stand-in the runner writes
    there is then found the same way a real source would be.

    The runfiles are rebuilt rather than filtered, there being no way to
    subtract from a `runfiles` object. Only the file list is pruned; the
    symlink maps are carried across as they came, having nothing in them
    a cache stands in for.
    """
    if not prunable:
        return dep_info

    runfiles = dep_info.runfiles
    return struct(
        transitive_imports = dep_info.transitive_imports,
        transitive_sources = depset(
            [
                file
                for file in dep_info.transitive_sources.to_list()
                if file.path not in prunable
            ],
            order = "postorder",
        ),
        runfiles = ctx.runfiles(
            files = [
                file
                for file in runfiles.files.to_list()
                if file.path not in prunable
            ],
            symlinks = runfiles.symlinks,
            root_symlinks = runfiles.root_symlinks,
        ),
    )

def _venv_env(ctx):
    """The action environment, with the hash seed pinned.

    Python randomizes the seed per process, and mypy's analysis is not
    entirely insensitive to the iteration order that follows from it: at
    least one numpy module gains or loses an attribute error depending
    on the seed. The errors mypy records go into the cache, so an
    unpinned seed leaves the artifact varying between runs on a single
    machine. Which seed is used does not matter, only that it is always
    the same one.

    Nothing here pins where the venv is built. The runner names every
    path it records relative to the venv's own runfiles tree, so the
    randomly named temporary directory the venv lands in does not reach
    the cache.
    """
    return ctx.configuration.default_shell_env | {
        "PYTHONHASHSEED": "0",
    }

def _typed_markers(ctx):
    """PEP 561 markers, which resolution consults before the cache.

    A package is only treated as typed if its `py.typed` is found, and
    that happens while mypy is still looking for the module, before it
    reaches any cached data. So consumers have to recreate these
    alongside the sources they stand in for.
    """
    return [
        file
        for file in getattr(ctx.rule.files, "data", [])
        if file.basename == "py.typed"
    ]

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _runner_attrs(cfg):
    """The attributes a rule needs to build a venv around the mypy runner.

    The configuration is the only thing that varies: `py_mypy_test` runs
    the runner as the test, where the cache-producing rules run it as a
    tool of the action.
    """
    return {
        "_runner": attr.label(
            doc = "The process wrapper for running mypy.",
            cfg = cfg,
            default = Label("//python/mypy/private:mypy_runner"),
        ),
        "_runner_main": attr.label(
            doc = "The main entrypoint for the mypy runner.",
            cfg = cfg,
            allow_single_file = True,
            default = Label("//python/mypy/private:mypy_runner.py"),
        ),
    }

def _py_mypy_test_impl(ctx):
    venv_toolchain = ctx.toolchains[py_venv_common.TOOLCHAIN_TYPE]

    # The test reports to a person, so it can be pointed at a different
    # config than the one the toolchain names. The caches cannot: their
    # entries are keyed on the settings that produced them, so the aspect
    # takes the toolchain's config and nothing else.
    config = ctx.file.config or ctx.toolchains[TOOLCHAIN_TYPE].config

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

    srcs = find_srcs(ctx.attr.target)

    # Captured rather than reached through `ctx`, so that the mapper
    # below holds a string rather than the whole rule context.
    workspace_name = ctx.workspace_name

    def _src_map(file):
        return _rlocationpath(file, workspace_name)

    # No `--cache-out`: this run reads no cache and writes none, so it has
    # no reason to insist on the one name a cache can be keyed by, and lets
    # the `imports` roots resolve imports the way the venv itself does.
    args = ctx.actions.args()
    args.set_param_file_format("multiline")
    args.add("--config-file", _rlocationpath(config, ctx.workspace_name))
    args.add("--workspace_name", ctx.workspace_name)
    args.add_all(
        srcs,
        map_each = _src_map,
        format_each = "--file=%s",
        allow_closure = True,
    )

    args_file = ctx.actions.declare_file("{}.mypy_args.txt".format(ctx.label.name))
    ctx.actions.write(
        output = args_file,
        content = args,
    )

    return [
        DefaultInfo(
            files = depset([executable]),
            runfiles = runfiles.merge(
                ctx.runfiles(files = [config, args_file]),
            ),
            executable = executable,
        ),
        RunEnvironmentInfo(
            environment = {
                "RULES_VENV_MYPY_RUNNER_ARGS_FILE": _rlocationpath(args_file, ctx.workspace_name),
            },
        ),
    ]

py_mypy_test = rule(
    implementation = _py_mypy_test_impl,
    doc = "A rule for running mypy on a Python target.",
    attrs = {
        "config": attr.label(
            doc = (
                "The config file (`mypy.ini`, `setup.cfg` or `pyproject.toml`) " +
                "containing mypy settings. A `.toml` file is read from its " +
                "`tool.mypy` table, anything else from its `[mypy]` section. " +
                "Defaults to the one the `py_mypy_toolchain` names."
            ),
            cfg = "target",
            allow_single_file = True,
        ),
        "target": attr.label(
            doc = "The target to run `mypy` on.",
            providers = [PyInfo],
            mandatory = True,
            aspects = [target_sources_aspect],
        ),
    } | _runner_attrs("target"),
    toolchains = [
        TOOLCHAIN_TYPE,
        py_venv_common.TOOLCHAIN_TYPE,
    ],
    test = True,
)

# The runner, as a cache-producing action needs it. Both the aspect and
# `py_mypy_stdlib_cache` build the same venv around it, so they take the
# same attributes to build it from.
_CACHE_RUNNER_ATTRS = _runner_attrs("exec")

# Bounds on what a mypy action is allowed to ask for, in MB.
#
# The floor is what mypy costs before it has read anything of the target,
# which is most of what a small one costs at all: across 130 measured
# actions the smallest peak was 110MB and the median 116MB. It is a floor
# rather than a term because the input count does not reliably include
# the interpreter -- a toolchain resolved to one the host already has
# installed is a single file -- and a count that small would otherwise
# reserve nothing at all for an action that still needs this much.
#
# The ceiling is there because the count is a poor proxy in the other
# direction too, and an action that happens to declare a great many
# inputs should not be able to reserve a whole machine on the strength of
# it. It sits well above the 373MB largest peak measured.
_MYPY_MIN_MEMORY = 256
_MYPY_MAX_MEMORY = 1024

def _mypy_resource_set(_os_name, inputs):
    """A `ctx.actions.run.resource_set` function for the mypy actions.

    What mypy costs is dominated by the cached type information it loads
    before it analyzes anything: peak memory rose roughly 2MB per
    dependency cache above the floor below, reaching 373MB at 113 caches.
    Source count barely registered next to it.

    A resource set is not shown any of that. It gets a count of the
    action's inputs, which today is dominated by the interpreter and
    mypy's own closure travelling with every one of these actions -- some
    7,300 files of the roughly 7,400 a typical action declares. The
    figure below is therefore per-input rather than per-dependency, and
    is the largest ratio observed across those actions, so it covers the
    worst of them rather than the median. It is due to be revisited when
    those tool inputs stop being shipped, because the count will then
    mean something quite different.

    mypy analyzes on one thread, and a cache is large enough to spend
    minutes on, so the CPU is claimed to keep a host from running one of
    these per core it has.

    Args:
        _os_name (str): The name of the exec operating system.
        inputs (int): The number of inputs to the action.

    Returns:
        dict: A mapping of resource name to their desired values.
    """
    return {
        "cpu": 1,
        # Note that the value is in MB.
        "memory": min(_MYPY_MAX_MEMORY, max(_MYPY_MIN_MEMORY, 0.05 * inputs)),
    }

def _cache_venv(ctx, venv_toolchain, dep_info, name):
    """Build the venv a cache-producing mypy action runs in.

    Every action that publishes a cache has to build its venv the same
    way, because mypy records the path of every file it reads into that
    file's cached data, and the interface hash a consumer checks a
    dependency against is taken over those bytes. Two actions that read
    the same file therefore have to name it the same way, and they can
    only do that while every file is somewhere the venv put it: one left
    where Bazel staged it is reached through the execution root, and so
    through the user's checkout and sandbox.

    That is also what lets a pruned repository stay pruned. A repo
    imported in place is read from the real thing, sources and all,
    where the stand-ins the runner writes would never be seen.

    Returns:
        Tuple[File, Runfiles]: The entrypoint and its runfiles.
    """
    py_info = py_venv_common.create_py_info(
        ctx = ctx,
        imports = [],
        srcs = [ctx.file._runner_main],
        dep_info = dep_info,
    )

    return py_venv_common.create_venv_entrypoint(
        ctx = ctx,
        venv_toolchain = venv_toolchain,
        py_info = py_info,
        main = ctx.file._runner_main,
        name = name,
        runfiles = dep_info.runfiles,
        use_runfiles_in_entrypoint = False,
        force_runfiles = True,
        use_source_deps_in_place = False,
    )

def _py_mypy_aspect_impl(target, ctx):
    config = ctx.toolchains[TOOLCHAIN_TYPE].config
    deps = _dep_caches(ctx)

    inherited = [PyMypyCacheInfo(caches = deps.caches, covered = deps.covered)]

    if PyInfo not in target:
        # Not a Python target, but it may still sit between two that are
        # -- a toolchain rule forwarding a library, say. Keep the chain
        # intact rather than stopping here, which would strand the
        # caches on the far side.
        return inherited

    # A target is checked only if it has first-party sources and has not
    # opted out. Everything else is still analyzed, so that consumers
    # have a cache to read instead of the sources, but its type errors
    # are not reported.
    checked = find_srcs(target, ctx).to_list()
    cache_only = _is_ignored(ctx) or not checked
    srcs = _unchecked_srcs(ctx) if cache_only else checked

    if not srcs and not deps.py_deps:
        # The target publishes Python that none of its attributes
        # explains: it forwards a library it reached some other way,
        # which is what toolchain resolution produces and what the
        # `current_py_*_toolchain` rules here are. The aspect cannot
        # follow that edge, so this is the only place the library gets
        # analyzed once instead of in every consumer.
        #
        # The whole closure is taken as a single unit rather than picked
        # apart, which is redundant where some of it is cached
        # elsewhere too, but it needs nothing of the rule beyond the
        # `PyInfo` it already returns. A rule with attributes to walk
        # keeps the finer-grained treatment; only the dead end takes
        # this one.
        srcs = _pick_modules(target[PyInfo].transitive_sources.to_list())

    if not srcs:
        return inherited

    markers = _typed_markers(ctx)

    venv_toolchain = py_venv_common.get_toolchain(ctx, cfg = "exec")

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner, target],
    )

    prunable = _prunable(ctx, deps.covered, srcs)
    dep_info = _prune_dep_info(ctx, dep_info, prunable)

    cache = ctx.actions.declare_file("{}.mypy.cache".format(target.label.name))
    aspect_name = "{}.mypy".format(target.label.name)

    executable, runfiles = _cache_venv(ctx, venv_toolchain, dep_info, aspect_name)

    args = ctx.actions.args()

    # A target deep in the graph gets one `--dep-cache` per transitive
    # dependency, which outgrows a command line. Always, rather than only
    # once Bazel judges the line too long: the limit that matters is
    # Windows' and it is small enough that a modest target reaches it.
    args.use_param_file("@%s", use_always = True)
    args.set_param_file_format("multiline")
    args.add("--config-file", config)
    args.add("--workspace_name", ctx.workspace_name)
    args.add("--cache-out", cache)

    # Nothing here says which files an `imports` root renames. The runner
    # reads the roots off the venv it is running in and looks under them,
    # which is the same answer for a fraction of the work: the roots are
    # the few directories some target asked to be searched, where this
    # would be every source in the closure, thousands of flags for a
    # target of any size.
    src_paths = [_rlocationpath(file, ctx.workspace_name) for file in srcs]
    args.add_all(src_paths, format_each = "--file=%s")
    args.add_all(
        src_paths + [_rlocationpath(file, ctx.workspace_name) for file in markers],
        format_each = "--manifest=%s",
    )

    args.add("--dep-cache", ctx.file._stdlib_cache)
    args.add_all(deps.caches, format_each = "--dep-cache=%s")

    outputs = [cache]
    marker = None
    if cache_only:
        args.add("--cache-only")
    else:
        marker = ctx.actions.declare_file("{}.mypy.ok".format(target.label.name))
        outputs.append(marker)
        args.add("--marker", marker)

    # A cache-only action and a checking one cost differently and fail
    # differently -- one reports nothing and is not allowed to fail the
    # build -- so they are told apart in the profile and on the console
    # rather than sharing a name and leaving which is which to be guessed.
    mnemonic = "PyMypyCache" if cache_only else "PyMypy"

    ctx.actions.run(
        mnemonic = mnemonic,
        progress_message = mnemonic + " %{label}",
        executable = executable,
        inputs = depset(
            [config, ctx.file._stdlib_cache] + srcs + markers,
            transitive = [deps.caches],
        ),
        tools = runfiles.files,
        outputs = outputs,
        arguments = [args],
        env = _venv_env(ctx),
        resource_set = _mypy_resource_set,
    )

    providers = [PyMypyCacheInfo(
        caches = depset([cache], transitive = [deps.caches]),
        covered = depset(
            _covered_files(ctx, srcs),
            transitive = [deps.covered],
        ),
    )]
    if marker:
        providers.append(OutputGroupInfo(py_mypy_checks = depset([marker])))
    return providers

py_mypy_aspect = aspect(
    implementation = _py_mypy_aspect_impl,
    doc = """\
An aspect for running mypy on targets with Python sources.

Every Python target the aspect reaches publishes a
[PyMypyCacheInfo](#pymypycacheinfo), including the ones it does not
check. Targets that opt out with a `no_mypy` tag, and third-party
packages, are analyzed but not reported on.

It travels every attribute rather than `deps` alone, since a rule is
free to build its `PyInfo` from any of them. A library reached through
a *toolchain* cannot be followed that way at all, so a target whose
Python none of its attributes accounts for caches everything it
publishes as one unit. That needs nothing of the rule but the `PyInfo`
it already returns, so a toolchain defined outside this repository gets
the same treatment without doing anything.""",
    attrs = _CACHE_RUNNER_ATTRS | {
        "_stdlib_cache": attr.label(
            doc = "Type information for the standard library, inherited by every action.",
            cfg = "target",
            allow_single_file = True,
            default = Label("//python/mypy:stdlib_cache"),
        ),
    } | py_venv_common.create_venv_attrs(),
    attr_aspects = _ATTR_ASPECTS,
    toolchains = [TOOLCHAIN_TYPE],
    requires = [target_sources_aspect],
)

def _py_mypy_stdlib_cache_impl(ctx):
    venv_toolchain = py_venv_common.get_toolchain(ctx, cfg = "exec")
    config = ctx.toolchains[TOOLCHAIN_TYPE].config

    dep_info = py_venv_common.create_dep_info(
        ctx = ctx,
        deps = [ctx.attr._runner],
    )

    # Every other mypy action inherits this cache, so typeshed has to be
    # named here the way they will name it.
    executable, runfiles = _cache_venv(
        ctx,
        venv_toolchain,
        dep_info,
        "{}.mypy".format(ctx.label.name),
    )

    cache = ctx.actions.declare_file("{}.mypy.cache".format(ctx.label.name))

    args = ctx.actions.args()
    args.add("--config-file", config)
    args.add("--workspace_name", ctx.workspace_name)
    args.add("--cache-out", cache)
    args.add("--cache-only")
    args.add("--stdlib")

    ctx.actions.run(
        mnemonic = "PyMypyStdlibCache",
        progress_message = "PyMypyStdlibCache %{label}",
        executable = executable,
        inputs = depset([config]),
        tools = runfiles.files,
        outputs = [cache],
        arguments = [args],
        env = _venv_env(ctx),
        resource_set = _mypy_resource_set,
    )

    return [
        DefaultInfo(files = depset([cache])),
        # The standard library is never staged in a venv to begin with,
        # so there is nothing here for a consumer to leave out.
        PyMypyCacheInfo(caches = depset([cache]), covered = depset()),
    ]

py_mypy_stdlib_cache = rule(
    implementation = _py_mypy_stdlib_cache_impl,
    doc = """\
Type information for the Python standard library.

Every mypy run pulls in the same typeshed core, so without this each
target's cache would carry its own copy of it and a large dependency
graph would ship the same stubs hundreds of times. Analyzing it once
here keeps it out of every other cache: entries inherited from a
dependency are never republished.""",
    attrs = _CACHE_RUNNER_ATTRS | py_venv_common.create_venv_attrs(),
    toolchains = [TOOLCHAIN_TYPE],
)
