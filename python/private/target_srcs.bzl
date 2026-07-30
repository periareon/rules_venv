"""A utility for collecting info from python targets useful for linting."""

load("@bazel_skylib//lib:paths.bzl", "paths")
load("//python:py_info.bzl", "PyInfo")

PySourcesInfo = provider(
    doc = "A container for info on a lintable python target.",
    fields = {
        "first_party_modules": """\
depset[str]: Top-level workspace path segments contributed by this target
and its transitive Python dependencies. Includes segments derived from
`.py` / `.pyi` sources and from compiled Python extension outputs
(`.so`, `.pyd`, `.dylib`).""",
        "imports": "depset[str]: The values of `PyInfo.imports` for the current target.",
        "srcs": "depset[File]: All direct source files.",
    },
)

_PY_SOURCE_SUFFIXES = [".py", ".pyi"]
_PY_EXTENSION_EXTENSIONS = [".so", ".pyd", ".dylib"]

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

def _strip_recognized_suffix(name):
    """Return `name` with a trailing `.py` / `.pyi` / `.so` / `.pyd` / `.dylib` stripped, or None."""
    for suffix in _PY_SOURCE_SUFFIXES + _PY_EXTENSION_EXTENSIONS:
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return None

def _first_party_module_from_file(file):
    """Return the top-level workspace module name for a Python-content File, or None to skip it."""
    short_path = file.short_path
    if short_path.startswith("../"):
        return None

    seg, sep, _ = short_path.partition("/")
    if not seg:
        return None

    if not sep:
        # Workspace-root file: strip a recognized Python suffix or skip.
        stripped = _strip_recognized_suffix(seg)
        if stripped == None:
            return None
        seg = stripped

    if not _is_valid_python_module_name(seg):
        return None
    return seg

def _collect_direct_first_party_segments(target, ctx):
    """Extract first-party segments this target itself contributes.

    Sources scanned:
      * `ctx.rule.files.srcs` — `.py` / `.pyi` sources (source or generated).
      * `target[DefaultInfo].files` — compiled extension outputs
        (`.so` / `.pyd` / `.dylib`) produced by rules like `py_cc_extension`.

    Segments are deduplicated locally so a target with many files under a
    single top-level dir contributes just one string to its depset node
    (parent nodes still dedupe across siblings via `uniquify` on the args).
    """
    extensions = [ext.strip(".") for ext in _PY_EXTENSION_EXTENSIONS]
    seen = {}
    for src in getattr(ctx.rule.files, "srcs", []):
        seg = _first_party_module_from_file(src)
        if seg:
            seen[seg] = None
    for out in target[DefaultInfo].files.to_list():
        if out.extension in extensions:
            seg = _first_party_module_from_file(out)
            if seg:
                seen[seg] = None
    return list(seen)

def find_srcs(target, aspect_ctx = None):
    """Find all lintable source files for a given target.

    Note that generated files are ignored.

    Args:
        target (Target): The target to collect from.
        aspect_ctx (ctx, optional): The context object for an aspect if called within one.

    Returns:
        depset[File]: A depset of lintable source files.
    """
    if PyInfo not in target:
        return depset()

    # Ignore any external targets
    if target.label.workspace_root.startswith("external"):
        return depset()

    if PySourcesInfo in target:
        # Use previous results of the `target_sources_aspect`.
        srcs = target[PySourcesInfo].srcs
    elif aspect_ctx:
        # If running in an aspect, we can directly check attributes
        srcs = depset([
            src
            for src in getattr(aspect_ctx.rule.files, "srcs", [])
            if src.is_source
        ])
    else:
        # No sources can be found.
        srcs = depset()

    return srcs

def _get_imports(target, aspect_ctx):
    """Get all usable import paths for a given target.

    Args:
        target (Target): The target to collect from.
        aspect_ctx (ctx, optional): The context object for an aspect if called within one.

    Returns:
        List of strings.
    """
    workspace_name = target.label.workspace_name
    if not workspace_name:
        workspace_name = aspect_ctx.workspace_name
    if not workspace_name:
        workspace_name = "_main"

    prefix = "{}/{}".format(
        workspace_name,
        target.label.package,
    )
    result = []
    for import_str in getattr(aspect_ctx.rule.attr, "imports", []):
        import_str = aspect_ctx.expand_make_variables("imports", import_str, {})
        if import_str.startswith("/"):
            continue

        # Relative paths are all normalized to help prevent sandbox escapes.
        import_path = paths.normalize("{}/{}".format(prefix, import_str))
        if import_path.startswith("../") or import_path == "..":
            fail("Import paths cannot refer to paths outside the execution root: `{}`".format(
                import_str,
            ))
        result.append(import_path)

    return result

def _target_sources_impl(target, ctx):
    if PySourcesInfo in target:
        return []

    srcs = find_srcs(target, aspect_ctx = ctx)
    transitive_modules = [
        dep[PySourcesInfo].first_party_modules
        for dep in getattr(ctx.rule.attr, "deps", [])
        if PySourcesInfo in dep
    ]

    workspace_name = target.label.workspace_name
    if workspace_name and workspace_name != ctx.workspace_name:
        # External-workspace target: keep the transitive rollup so parents
        # can reach through, but contribute nothing of our own.
        imports = depset()
        direct_segments = []
    else:
        workspace_name = workspace_name or "_main"
        imports = depset([workspace_name] + _get_imports(target, ctx))
        direct_segments = _collect_direct_first_party_segments(target, ctx)

    return [PySourcesInfo(
        srcs = srcs,
        imports = imports,
        first_party_modules = depset(direct_segments, transitive = transitive_modules),
    )]

target_sources_aspect = aspect(
    implementation = _target_sources_impl,
    attr_aspects = ["deps"],
    doc = """\
Walks the dependency tree of a lintable Python target and attaches a
`PySourcesInfo` provider to each visited node. The provider carries
per-target `srcs` and `imports` plus a transitively-rolled-up
`first_party_modules` depset that downstream lint aspects (ruff, isort,
mypy, pylint, ty) can consume directly without repeating the walk.""",
)
