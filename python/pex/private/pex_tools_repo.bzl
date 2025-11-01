"""Scie tools repository rules"""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_file")
load("//python/pex/private:pex_versions.bzl", _PEX_VERSIONS = "PEX_VERSIONS")
load("//python/pex/private:scie_jump_versions.bzl", _SCIE_JUMP_VERSIONS = "SCIE_JUMP_VERSIONS")
load("//python/pex/private:scie_ptex_versions.bzl", _SCIE_PTEX_VERSIONS = "SCIE_PTEX_VERSIONS")
load("//python/pex/private:scie_python_versions.bzl", _PYTHON_BUILD_STANDALONE_VERSIONS = "PYTHON_BUILD_STANDALONE_VERSIONS")
load("//python/pex/private:scie_science_versions.bzl", _SCIE_SCIENCE_VERSIONS = "SCIE_SCIENCE_VERSIONS")

PEX_DEFAULT_VERSION = "2.67.3"
SCIE_SCIENCE_DEFAULT_VERSION = "0.15.0"
SCIE_JUMP_DEFAULT_VERSION = "1.8.0"
SCIE_PTEX_DEFAULT_VERSION = "1.7.0"
PYTHON_BUILD_STANDALONE_DEFAULT_VERSION = "3.11"

PEX_VERSIONS = _PEX_VERSIONS
SCIE_SCIENCE_VERSIONS = _SCIE_SCIENCE_VERSIONS
SCIE_JUMP_VERSIONS = _SCIE_JUMP_VERSIONS
SCIE_PTEX_VERSIONS = _SCIE_PTEX_VERSIONS
PYTHON_BUILD_STANDALONE_VERSIONS = _PYTHON_BUILD_STANDALONE_VERSIONS

CONSTRAINTS = {
    "linux-aarch64": ["@platforms//os:linux", "@platforms//cpu:aarch64"],
    "linux-armv7l": ["@platforms//os:linux", "@platforms//cpu:armv7"],
    "linux-powerpc64": ["@platforms//os:linux", "@platforms//cpu:ppc64le"],
    "linux-riscv64": ["@platforms//os:linux", "@platforms//cpu:riscv64"],
    "linux-s390x": ["@platforms//os:linux", "@platforms//cpu:s390x"],
    "linux-x86_64": ["@platforms//os:linux", "@platforms//cpu:x86_64"],
    "macos-aarch64": ["@platforms//os:macos", "@platforms//cpu:aarch64"],
    "macos-x86_64": ["@platforms//os:macos", "@platforms//cpu:x86_64"],
    "windows-x86_64": ["@platforms//os:windows", "@platforms//cpu:x86_64"],
}

def _scie_tool_repository(*, name, urls, integrity, **kwargs):
    """Download a version of a scie tool binary for a platform.

    Args:
        name (str): The name of the repository to create.
        urls (list): The URLs for fetching the scie tool binary.
        integrity (str): The integrity checksum of the scie tool binary.
        **kwargs (dict): Additional keyword arguments.

    Returns:
        str: Return `name` for convenience.
    """

    # Extract basename from URL
    if not urls:
        fail("At least one URL must be provided")
    url_path = urls[0].split("/")[-1]

    # Remove query parameters if present
    url_path = url_path.split("?")[0]
    binary_name = url_path

    http_file(
        name = name,
        urls = urls,
        integrity = integrity,
        downloaded_file_path = binary_name,
        executable = True,
        **kwargs
    )

    return name

def scie_science_repository(*, name, platform, urls, integrity, **kwargs):
    """Download a version of scie science binary for a platform.

    Args:
        name: Repository name.
        platform: Target platform (informational only).
        urls: Download URLs.
        integrity: File integrity hash.
        **kwargs: Additional arguments.
    """

    # Note: platform parameter is kept for API compatibility but the actual
    # platform is determined from the URL content
    if not platform:
        fail("platform must be specified")
    return _scie_tool_repository(
        name = name,
        urls = urls,
        integrity = integrity,
        **kwargs
    )

def scie_jump_repository(*, name, platform, urls, integrity, **kwargs):
    """Download a version of scie jump binary for a platform.

    Args:
        name: Repository name.
        platform: Target platform (informational only).
        urls: Download URLs.
        integrity: File integrity hash.
        **kwargs: Additional arguments.
    """

    # Note: platform parameter is kept for API compatibility but the actual
    # platform is determined from the URL content
    if not platform:
        fail("platform must be specified")
    return _scie_tool_repository(
        name = name,
        urls = urls,
        integrity = integrity,
        **kwargs
    )

def scie_ptex_repository(*, name, platform, urls, integrity, **kwargs):
    """Download a version of scie ptex binary for a platform.

    Args:
        name: Repository name.
        platform: Target platform (informational only).
        urls: Download URLs.
        integrity: File integrity hash.
        **kwargs: Additional arguments.
    """

    # Note: platform parameter is kept for API compatibility but the actual
    # platform is determined from the URL content
    if not platform:
        fail("platform must be specified")
    return _scie_tool_repository(
        name = name,
        urls = urls,
        integrity = integrity,
        **kwargs
    )

def pex_repository(*, name, platform, urls, integrity, **kwargs):
    """Download a version of pex binary for a platform.

    Args:
        name: Repository name.
        platform: Target platform (informational only).
        urls: Download URLs.
        integrity: File integrity hash.
        **kwargs: Additional arguments.
    """

    # Note: platform parameter is kept for API compatibility but the actual
    # platform is determined from the URL content
    if not platform:
        fail("platform must be specified")
    return _scie_tool_repository(
        name = name,
        urls = urls,
        integrity = integrity,
        **kwargs
    )

_ALIAS_TEMPLATE = """\
alias(
    name = "{}",
    actual = "{}",
    visibility = ["//visibility:public"],
)
"""

def _scie_tool_repository_hub_impl(repository_ctx):
    """Implementation for scie tool repository hub."""
    repository_ctx.file("WORKSPACE.bazel", """workspace(name = "{}")""".format(
        repository_ctx.name,
    ))

    # Create alias targets for each platform binary
    aliases = []
    for platform, label in repository_ctx.attr.platforms_to_binaries.items():
        aliases.append(_ALIAS_TEMPLATE.format(
            platform,
            label,
        ))

    repository_ctx.file("BUILD.bazel", "\n".join(aliases))

scie_science_repository_hub = repository_rule(
    doc = "Generates a repository with aliases for each platform-specific scie science binary.",
    attrs = {
        "platforms_to_binaries": attr.string_dict(
            doc = "A mapping of platforms to scie science labels.",
            mandatory = True,
        ),
    },
    implementation = _scie_tool_repository_hub_impl,
)

scie_jump_repository_hub = repository_rule(
    doc = "Generates a repository with aliases for each platform-specific scie jump binary.",
    attrs = {
        "platforms_to_binaries": attr.string_dict(
            doc = "A mapping of platforms to scie jump labels.",
            mandatory = True,
        ),
    },
    implementation = _scie_tool_repository_hub_impl,
)

scie_ptex_repository_hub = repository_rule(
    doc = "Generates a repository with aliases for each platform-specific scie ptex binary.",
    attrs = {
        "platforms_to_binaries": attr.string_dict(
            doc = "A mapping of platforms to scie ptex labels.",
            mandatory = True,
        ),
    },
    implementation = _scie_tool_repository_hub_impl,
)

pex_repository_hub = repository_rule(
    doc = "Generates a repository with aliases for each platform-specific pex binary.",
    attrs = {
        "platforms_to_binaries": attr.string_dict(
            doc = "A mapping of platforms to pex labels.",
            mandatory = True,
        ),
    },
    implementation = _scie_tool_repository_hub_impl,
)

_TOOLCHAIN_TEMPLATE = """\
py_pex_toolchain(
    name = "{toolchain_name}",
    pex = "{pex}",
    platform = "{scie_platform}",
    scie_science = "{scie_science}",
    scie_jump = "{scie_jump}",
    scie_ptex = "{scie_ptex}",
    scie_python_interpreter = "{python_interpreter}",
    scie_python_version = "{python_version}",
    visibility = ["//visibility:public"],
)
"""

_TOOLCHAIN_BUILD_TEMPLATE = """\
load("@rules_venv//python/pex:defs.bzl", "py_pex_toolchain")

{toolchains}
"""

def _pex_toolchain_repository_impl(repository_ctx):
    """Implementation for pex toolchain repository."""
    repository_ctx.file("WORKSPACE.bazel", """workspace(name = "{}")""".format(
        repository_ctx.name,
    ))

    toolchain_impls = []

    # Generate toolchains for every combination of (scie_platform, python_platform)
    for scie_platform in repository_ctx.attr.scie_platforms:
        for python_platform in repository_ctx.attr.python_platforms:
            toolchain_name = "py_pex_toolchain_{scie_platform}_{python_platform}".format(
                scie_platform = scie_platform,
                python_platform = python_platform,
            )

            # Get Python interpreter info for this platform
            python_interpreter = repository_ctx.attr.python_interpreters.get(python_platform, "")

            toolchain_impls.append(_TOOLCHAIN_TEMPLATE.format(
                toolchain_name = toolchain_name,
                pex = repository_ctx.attr.pex_binaries.get(scie_platform, ""),
                scie_platform = scie_platform,
                scie_science = repository_ctx.attr.scie_science_binaries.get(scie_platform, ""),
                scie_jump = repository_ctx.attr.scie_jump_binaries.get(scie_platform, ""),
                scie_ptex = repository_ctx.attr.scie_ptex_binaries.get(scie_platform, ""),
                python_interpreter = python_interpreter,
                python_version = repository_ctx.attr.python_version,
            ))

    repository_ctx.file("BUILD.bazel", _TOOLCHAIN_BUILD_TEMPLATE.format(
        toolchains = "\n".join(toolchain_impls),
    ))

pex_toolchain_repository = repository_rule(
    doc = "Generates a repository with py_pex_toolchain targets for each (scie_platform, python_platform) combination.",
    attrs = {
        "pex_binaries": attr.string_dict(
            doc = "A mapping of scie platform to pex binary label.",
            mandatory = True,
        ),
        "python_integrities": attr.string_dict(
            doc = "A mapping of Python platform to Python interpreter integrity.",
            mandatory = True,
        ),
        "python_interpreters": attr.string_dict(
            doc = "A mapping of Python platform to Python interpreter label.",
            mandatory = True,
        ),
        "python_platforms": attr.string_list(
            doc = "List of Python platforms to create toolchains for.",
            mandatory = True,
        ),
        "python_version": attr.string(
            doc = "The Python version string (e.g., '3.11').",
            mandatory = True,
        ),
        "scie_jump_binaries": attr.string_dict(
            doc = "A mapping of scie platform to scie jump binary label.",
            mandatory = True,
        ),
        "scie_platforms": attr.string_list(
            doc = "List of scie platforms to create toolchains for.",
            mandatory = True,
        ),
        "scie_ptex_binaries": attr.string_dict(
            doc = "A mapping of scie platform to scie ptex binary label.",
            mandatory = True,
        ),
        "scie_science_binaries": attr.string_dict(
            doc = "A mapping of scie platform to scie science binary label.",
            mandatory = True,
        ),
    },
    implementation = _pex_toolchain_repository_impl,
)

_HUB_TOOLCHAIN_TEMPLATE = """\
toolchain(
    name = "toolchain_{toolchain_key}",
    toolchain = "{toolchain_label}",
    toolchain_type = "@rules_venv//python/pex:toolchain_type",
    exec_compatible_with = {exec_compatible_with},
    target_compatible_with = {target_compatible_with},
    visibility = ["//visibility:public"],
)
"""

def _pex_toolchain_repository_hub_impl(repository_ctx):
    """Implementation for pex toolchain repository hub."""
    repository_ctx.file("WORKSPACE.bazel", """workspace(name = "{}")""".format(
        repository_ctx.name,
    ))

    toolchains = []
    for toolchain_key, toolchain_label in repository_ctx.attr.toolchain_labels.items():
        # toolchain_key is "{scie_platform}_{python_platform}"
        exec_constraints = repository_ctx.attr.exec_constraints.get(toolchain_key, [])
        target_constraints = repository_ctx.attr.target_constraints.get(toolchain_key, [])

        exec_constraint_list = json.encode(exec_constraints)
        target_constraint_list = json.encode(target_constraints)

        toolchains.append(_HUB_TOOLCHAIN_TEMPLATE.format(
            toolchain_key = toolchain_key,
            toolchain_label = toolchain_label,
            exec_compatible_with = exec_constraint_list,
            target_compatible_with = target_constraint_list,
        ))

    repository_ctx.file("BUILD.bazel", "\n".join(toolchains))

pex_toolchain_repository_hub = repository_rule(
    doc = "Generates a repository with toolchain targets for each (scie_platform, python_platform) combination with appropriate constraints.",
    attrs = {
        "exec_constraints": attr.string_list_dict(
            doc = "A mapping of '{scie_platform}_{python_platform}' to list of exec_compatible_with constraints.",
            mandatory = True,
        ),
        "target_constraints": attr.string_list_dict(
            doc = "A mapping of '{scie_platform}_{python_platform}' to list of target_compatible_with constraints.",
            mandatory = True,
        ),
        "toolchain_labels": attr.string_dict(
            doc = "A mapping of '{scie_platform}_{python_platform}' to py_pex_toolchain label.",
            mandatory = True,
        ),
    },
    implementation = _pex_toolchain_repository_hub_impl,
)
