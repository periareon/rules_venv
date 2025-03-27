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
    """Parse a target for it's sources to run on.

    Args:
        target (Target): The target the aspect is running on.
        aspect_ctx (ctx, optional): The aspect's context object.

    Returns:
        depset[File]: A depset of sources.
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

    elif PySourcesInfo not in target:
        srcs = depset()
    else:
        srcs = target[PySourcesInfo].srcs

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

def _target_sources_impl(target, ctx):
    srcs = find_srcs(target, aspect_ctx = ctx)

    # Only collect imports for the current workspace to indicate which paths
    # are known first party packages.
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
