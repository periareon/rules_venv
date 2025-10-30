"""Pex Bzlmod Extensions"""

load(
    "//python/pex/private:scie_science_repo.bzl",
    "SCIE_SCIENCE_DEFAULT_VERSION",
    "SCIE_SCIENCE_VERSIONS",
    "scie_science_repository",
    "scie_science_repository_hub",
)

def _scie_science_impl(module_ctx):
    reproducible = True

    # Process all modules, not just the root
    for mod in module_ctx.modules:
        for attrs in mod.tags.scie_science:
            if attrs.version not in SCIE_SCIENCE_VERSIONS:
                fail("Scie science repository `{}` was given unsupported version `{}`. Try: {}".format(
                    attrs.name,
                    attrs.version,
                    sorted(SCIE_SCIENCE_VERSIONS.keys()),
                ))
            available = SCIE_SCIENCE_VERSIONS[attrs.version]

            plat_to_label = {}
            for platform, binary_info in available.items():
                plat_to_label[platform] = "@{}//file".format(
                    scie_science_repository(
                        name = "{}_{}_{}".format(attrs.name, attrs.version, platform),
                        platform = platform,
                        urls = [binary_info["url"]],
                        integrity = binary_info["integrity"],
                    ),
                )

            scie_science_repository_hub(
                name = attrs.name,
                platforms_to_binaries = plat_to_label,
            )

    return module_ctx.extension_metadata(
        reproducible = reproducible,
    )

_SCIE_SCIENCE_TAG = tag_class(
    doc = """\
An extension for defining a scie science binary repository.

An example of defining and using scie science:

```python
pex = use_extension("//python/pex:extensions.bzl", "pex")
pex.scie_science(
    name = "scie_science",
    version = "0.15.0",
)
use_repo(pex, "scie_science")
```
""",
    attrs = {
        "name": attr.string(
            doc = "The name of the repository.",
            mandatory = True,
        ),
        "version": attr.string(
            doc = "The version of scie science to download.",
            default = SCIE_SCIENCE_DEFAULT_VERSION,
        ),
    },
)

pex = module_extension(
    doc = "Bzlmod extensions for Pex",
    implementation = _scie_science_impl,
    tag_classes = {
        "scie_science": _SCIE_SCIENCE_TAG,
    },
)
