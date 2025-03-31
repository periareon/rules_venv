"""A utility for collecting info from python targets useful for linting."""

load("@bazel_skylib//lib:paths.bzl", "paths")
load("//python:defs.bzl", "PyInfo")

PySourcesInfo = provider(
    doc = "A container for info on a lintable python target.",
    fields = {
        "imports": "Depset[str]: The values of `PyInfo.imports` for the current target.",
        "srcs": "depset[File]: All direct source files.",
    },
)

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

    if aspect_ctx:
        # If running in an aspect, we can directly check attributes
        srcs = depset([
            src
            for src in getattr(aspect_ctx.rule.files, "srcs", [])
            if src.is_source
        ])

    elif PySourcesInfo in target:
        # Use previous results of the `target_sources_aspect`.
        srcs = target[PySourcesInfo].srcs
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
    srcs = find_srcs(target, aspect_ctx = ctx)

    # Targets from external workspaces are ignored and given empty results.
    workspace_name = target.label.workspace_name
    if workspace_name and workspace_name != ctx.workspace_name:
        return [PySourcesInfo(
            srcs = srcs,
            imports = depset(),
        )]

    if not workspace_name:
        workspace_name = "_main"

    imports = depset([workspace_name] + _get_imports(target, ctx))

    return [PySourcesInfo(
        srcs = srcs,
        imports = imports,
    )]

target_sources_aspect = aspect(
    implementation = _target_sources_impl,
    doc = "An aspect for gathering additional data on a lintable target.",
    provides = [PySourcesInfo],
)
