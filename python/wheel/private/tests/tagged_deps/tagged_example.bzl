"""A repository rule rendering the targets of a wheel repository, to depend on from a wheel.

Only a target from another repository is a requirement of a wheel, and what
the repository of a wheel looks like depends on the rules that fetched it, so
one is rendered here with the three kinds of target a wheel may depend on: one
tagged with the distribution it was installed from, as `rules_python` and
`rules_req_compile` tag theirs, one carrying only the `.dist-info` directory of
the wheel, as the repositories of their older versions do, and one that says
nothing about it.
"""

_BUILD = """\
load("{defs}", "py_library")

package(default_visibility = ["//visibility:public"])

# A target of a `rules_req_compile` hub: named `<hub>.<package>` and tagged
# with the distribution, spelled differently from the target and the constraints.
py_library(
    name = "pip_deps.fancy_pkg",
    srcs = ["fancy_pkg.py"],
    imports = ["."],
    tags = [
        "manual",
        "pypi_name=Fancy-Pkg",
        "pypi_version=1.2.3",
    ],
)

# A target of an older hub: untagged, but with the `.dist-info` directory the
# wheel was installed with among its data, spelled unlike the constraints.
py_library(
    name = "pip_deps.dist_info_pkg",
    srcs = ["site-packages/dist_info_pkg.py"],
    data = glob(["site-packages/*.dist-info/**"]),
    imports = ["site-packages"],
    tags = ["manual"],
)

# A target without the tag, whose distribution can only be guessed from its name.
py_library(
    name = "pip_deps.plain",
    srcs = ["plain.py"],
    imports = ["."],
)
"""

def _tagged_example_repository_impl(repository_ctx):
    repository_ctx.file(
        "BUILD.bazel",
        _BUILD.format(defs = str(Label("//python:defs.bzl"))),
    )
    repository_ctx.file("fancy_pkg.py", '"""A module of the `Fancy-Pkg` distribution."""\n')
    repository_ctx.file(
        "site-packages/dist_info_pkg.py",
        '"""A module of the `Dist_Info_Pkg` distribution."""\n',
    )
    repository_ctx.file(
        "site-packages/Dist_Info_Pkg-3.4.5.dist-info/METADATA",
        "Metadata-Version: 2.1\nName: Dist_Info_Pkg\nVersion: 3.4.5\n",
    )
    repository_ctx.file("plain.py", '"""A module of a distribution the target does not name."""\n')

tagged_example_repository = repository_rule(
    doc = "Render the targets of a wheel repository: tagged with its distribution, carrying its `.dist-info`, and neither.",
    implementation = _tagged_example_repository_impl,
)
