"""Scie Science repository rules"""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_file")
load("//python/pex/private:scie_science_versions.bzl", _SCIE_SCIENCE_VERSIONS = "SCIE_SCIENCE_VERSIONS")

SCIE_SCIENCE_DEFAULT_VERSION = "0.15.0"

SCIE_SCIENCE_VERSIONS = _SCIE_SCIENCE_VERSIONS

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

def scie_science_repository(*, name, platform, urls, integrity, **kwargs):
    """Download a version of scie science binary for a platform.

    Args:
        name (str): The name of the repository to create.
        platform (str): The target platform of the scie science binary.
        urls (list): The URLs for fetching the scie science binary.
        integrity (str): The integrity checksum of the scie science binary.
        **kwargs (dict): Additional keyword arguments.

    Returns:
        str: Return `name` for convenience.
    """
    binary_name = "science-fat"
    if platform.startswith("windows"):
        binary_name += ".exe"

    http_file(
        name = name,
        urls = urls,
        integrity = integrity,
        downloaded_file_path = binary_name,
        executable = True,
        **kwargs
    )

    return name

_HUB_BUILD_CONTENT = """\

BINARIES = {binaries}

alias(
    name = "{name}",
    actual = select(BINARIES),
    visibility = ["//visibility:public"]
)
"""

def _scie_science_repository_hub_impl(repository_ctx):
    repository_ctx.file("WORKSPACE.bazel", """workspace(name = "{}")""".format(
        repository_ctx.name,
    ))

    binaries = {
        "@rules_venv//python/pex/constraints:{}".format(platform): target
        for platform, target in repository_ctx.attr.platforms_to_binaries.items()
    }

    repository_ctx.file("BUILD.bazel", _HUB_BUILD_CONTENT.format(
        binaries = json.encode_indent(binaries, indent = " " * 4),
        name = repository_ctx.original_name,
    ))

scie_science_repository_hub = repository_rule(
    doc = "Generates a repository that uses select() to expose the right scie science binary based on platform constraints.",
    attrs = {
        "platforms_to_binaries": attr.string_dict(
            doc = "A mapping of platforms to scie science labels.",
            mandatory = True,
        ),
    },
    implementation = _scie_science_repository_hub_impl,
)
