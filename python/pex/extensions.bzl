"""Pex Bzlmod Extensions"""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_file")
load(
    "//python/pex/private:pex_tools_repo.bzl",
    "CONSTRAINTS",
    "PEX_DEFAULT_VERSION",
    "PEX_VERSIONS",
    "PYTHON_BUILD_STANDALONE_DEFAULT_VERSION",
    "PYTHON_BUILD_STANDALONE_VERSIONS",
    "SCIE_JUMP_DEFAULT_VERSION",
    "SCIE_JUMP_VERSIONS",
    "SCIE_PTEX_DEFAULT_VERSION",
    "SCIE_PTEX_VERSIONS",
    "SCIE_SCIENCE_DEFAULT_VERSION",
    "SCIE_SCIENCE_VERSIONS",
    "pex_repository",
    "pex_repository_hub",
    "pex_toolchain_repository",
    "pex_toolchain_repository_hub",
    "scie_jump_repository",
    "scie_jump_repository_hub",
    "scie_ptex_repository",
    "scie_ptex_repository_hub",
    "scie_science_repository",
    "scie_science_repository_hub",
)

def _pex_toolchain_impl(module_ctx):
    reproducible = True

    # Collect all toolchain configurations
    for mod in module_ctx.modules:
        for attrs in mod.tags.toolchain:
            python_version = attrs.python_version

            if not python_version:
                fail("python_version is required for pex.toolchain")

            # Determine versions to use
            pex_version = attrs.pex_version or PEX_DEFAULT_VERSION
            scie_science_version = attrs.scie_science_version or SCIE_SCIENCE_DEFAULT_VERSION
            scie_jump_version = attrs.scie_jump_version or SCIE_JUMP_DEFAULT_VERSION
            scie_ptex_version = attrs.scie_ptex_version or SCIE_PTEX_DEFAULT_VERSION

            # Validate versions
            if pex_version not in PEX_VERSIONS:
                fail("Pex version `{}` is not supported. Try: {}".format(
                    pex_version,
                    sorted(PEX_VERSIONS.keys()),
                ))
            if scie_science_version not in SCIE_SCIENCE_VERSIONS:
                fail("Scie science version `{}` is not supported. Try: {}".format(
                    scie_science_version,
                    sorted(SCIE_SCIENCE_VERSIONS.keys()),
                ))
            if scie_jump_version not in SCIE_JUMP_VERSIONS:
                fail("Scie jump version `{}` is not supported. Try: {}".format(
                    scie_jump_version,
                    sorted(SCIE_JUMP_VERSIONS.keys()),
                ))
            if scie_ptex_version not in SCIE_PTEX_VERSIONS:
                fail("Scie ptex version `{}` is not supported. Try: {}".format(
                    scie_ptex_version,
                    sorted(SCIE_PTEX_VERSIONS.keys()),
                ))

            # Load Python versions and validate
            python_versions = PYTHON_BUILD_STANDALONE_VERSIONS
            if python_version not in python_versions:
                fail("Python version `{}` is not supported. Try: {}".format(
                    python_version,
                    sorted(python_versions.keys()),
                ))

            # Get available platforms from versions
            pex_available = PEX_VERSIONS[pex_version]
            science_available = SCIE_SCIENCE_VERSIONS[scie_science_version]
            jump_available = SCIE_JUMP_VERSIONS[scie_jump_version]
            ptex_available = SCIE_PTEX_VERSIONS[scie_ptex_version]
            python_available = python_versions[python_version]

            # Create repositories for each tool and platform
            pex_platforms_to_binaries = {}
            science_platforms_to_binaries = {}
            jump_platforms_to_binaries = {}
            ptex_platforms_to_binaries = {}

            # Filter to only non-windows platforms (pex doesn't support windows)
            scie_platforms = [p for p in science_available.keys() if not p.startswith("windows")]
            python_platforms = [p for p in python_available.keys() if not p.startswith("windows")]

            # Create Python interpreter repositories for each platform
            python_interpreters = {}
            python_integrities = {}
            for python_platform in python_platforms:
                if python_platform in python_available:
                    python_repo_name = "{}_python_{}_{}".format(attrs.name, python_version, python_platform)
                    python_info = python_available[python_platform]

                    # Extract basename from URL for downloaded_file_path
                    # URL format: https://github.com/.../cpython-X.Y.Z+DATE-platform-install_only.tar.gz
                    url_path = python_info["url"].split("/")[-1]
                    http_file(
                        name = python_repo_name,
                        urls = [python_info["url"]],
                        integrity = python_info["integrity"],
                        downloaded_file_path = url_path,
                    )
                    python_interpreters[python_platform] = "@{}//file".format(python_repo_name)
                    python_integrities[python_platform] = python_info["integrity"]

            for platform in scie_platforms:
                # Pex
                if platform in pex_available:
                    pex_repo_name = "{}_pex_{}_{}".format(attrs.name, pex_version, platform)
                    pex_repository(
                        name = pex_repo_name,
                        platform = platform,
                        urls = [pex_available[platform]["url"]],
                        integrity = pex_available[platform]["integrity"],
                    )
                    pex_platforms_to_binaries[platform] = "@{}//file".format(pex_repo_name)

                # Science
                if platform in science_available:
                    science_repo_name = "{}_science_{}_{}".format(attrs.name, scie_science_version, platform)
                    scie_science_repository(
                        name = science_repo_name,
                        platform = platform,
                        urls = [science_available[platform]["url"]],
                        integrity = science_available[platform]["integrity"],
                    )
                    science_platforms_to_binaries[platform] = "@{}//file".format(science_repo_name)

                # Jump
                if platform in jump_available:
                    jump_repo_name = "{}_jump_{}_{}".format(attrs.name, scie_jump_version, platform)
                    scie_jump_repository(
                        name = jump_repo_name,
                        platform = platform,
                        urls = [jump_available[platform]["url"]],
                        integrity = jump_available[platform]["integrity"],
                    )
                    jump_platforms_to_binaries[platform] = "@{}//file".format(jump_repo_name)

                # Ptex
                if platform in ptex_available:
                    ptex_repo_name = "{}_ptex_{}_{}".format(attrs.name, scie_ptex_version, platform)
                    scie_ptex_repository(
                        name = ptex_repo_name,
                        platform = platform,
                        urls = [ptex_available[platform]["url"]],
                        integrity = ptex_available[platform]["integrity"],
                    )
                    ptex_platforms_to_binaries[platform] = "@{}//file".format(ptex_repo_name)

            # Create hub repositories for each tool
            pex_hub_name = "{}_pex".format(attrs.name)
            pex_repository_hub(
                name = pex_hub_name,
                platforms_to_binaries = pex_platforms_to_binaries,
            )

            scie_science_hub_name = "{}_science".format(attrs.name)
            scie_science_repository_hub(
                name = scie_science_hub_name,
                platforms_to_binaries = science_platforms_to_binaries,
            )

            scie_jump_hub_name = "{}_jump".format(attrs.name)
            scie_jump_repository_hub(
                name = scie_jump_hub_name,
                platforms_to_binaries = jump_platforms_to_binaries,
            )

            scie_ptex_hub_name = "{}_ptex".format(attrs.name)
            scie_ptex_repository_hub(
                name = scie_ptex_hub_name,
                platforms_to_binaries = ptex_platforms_to_binaries,
            )

            # Create pex_toolchain_repository with platform-specific toolchains
            pex_binaries = {
                platform: "@{}//:{}".format(pex_hub_name, platform)
                for platform in scie_platforms
            }
            scie_science_binaries = {
                platform: "@{}//:{}".format(scie_science_hub_name, platform)
                for platform in scie_platforms
            }
            scie_jump_binaries = {
                platform: "@{}//:{}".format(scie_jump_hub_name, platform)
                for platform in scie_platforms
            }
            scie_ptex_binaries = {
                platform: "@{}//:{}".format(scie_ptex_hub_name, platform)
                for platform in scie_platforms
            }

            pex_toolchain_repo_name = "{}_toolchains".format(attrs.name)
            pex_toolchain_repository(
                name = pex_toolchain_repo_name,
                pex_binaries = pex_binaries,
                scie_platforms = scie_platforms,
                python_platforms = python_platforms,
                python_version = python_version,
                scie_science_binaries = scie_science_binaries,
                scie_jump_binaries = scie_jump_binaries,
                scie_ptex_binaries = scie_ptex_binaries,
                python_interpreters = python_interpreters,
                python_integrities = python_integrities,
            )

            # Create pex_toolchain_repository_hub with toolchain targets for every combination
            toolchain_labels = {}
            exec_constraints_dict = {}
            target_constraints_dict = {}

            for scie_platform in scie_platforms:
                for python_platform in python_platforms:
                    toolchain_key = "{}_{}".format(scie_platform, python_platform)
                    toolchain_labels[toolchain_key] = "@{}//:py_pex_toolchain_{}_{}".format(
                        pex_toolchain_repo_name,
                        scie_platform,
                        python_platform,
                    )

                    # exec_compatible_with uses scie platform constraints
                    exec_constraints_dict[toolchain_key] = CONSTRAINTS[scie_platform]

                    # target_compatible_with uses python platform constraints (same platform constraints)
                    target_constraints_dict[toolchain_key] = CONSTRAINTS[python_platform]

            pex_toolchain_repository_hub(
                name = attrs.name,
                toolchain_labels = toolchain_labels,
                exec_constraints = exec_constraints_dict,
                target_constraints = target_constraints_dict,
            )

    return module_ctx.extension_metadata(
        reproducible = reproducible,
    )

_TOOLCHAIN_TAG = tag_class(
    doc = """\
An extension for defining a pex toolchain.

An example of defining and using a pex toolchain:

```python
pex = use_extension("//python/pex:extensions.bzl", "pex")
pex.toolchain(
    name = "pex_toolchains",
    pex_version = "2.67.3",
    python_version = "3.11",
    scie_science_version = "0.15.0",
    scie_jump_version = "0.15.0",
    scie_ptex_version = "0.15.0",
)
use_repo(pex, "pex_toolchains")
```
""",
    attrs = {
        "name": attr.string(
            doc = "The name of the repository hub to create.",
            mandatory = True,
        ),
        "pex_version": attr.string(
            doc = "The version of pex to download.",
            default = PEX_DEFAULT_VERSION,
            values = PEX_VERSIONS.keys(),
        ),
        "python_version": attr.string(
            doc = "The Python version (e.g., '3.11').",
            default = PYTHON_BUILD_STANDALONE_DEFAULT_VERSION,
            values = PYTHON_BUILD_STANDALONE_VERSIONS.keys(),
        ),
        "scie_jump_version": attr.string(
            doc = "The version of scie jump to download.",
            default = SCIE_JUMP_DEFAULT_VERSION,
            values = SCIE_JUMP_VERSIONS.keys(),
        ),
        "scie_ptex_version": attr.string(
            doc = "The version of scie ptex to download.",
            default = SCIE_PTEX_DEFAULT_VERSION,
            values = SCIE_PTEX_VERSIONS.keys(),
        ),
        "scie_science_version": attr.string(
            doc = "The version of scie science to download.",
            default = SCIE_SCIENCE_DEFAULT_VERSION,
            values = SCIE_SCIENCE_VERSIONS.keys(),
        ),
    },
)

pex = module_extension(
    doc = "Bzlmod extensions for Pex",
    implementation = _pex_toolchain_impl,
    tag_classes = {
        "toolchain": _TOOLCHAIN_TAG,
    },
)
