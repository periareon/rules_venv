"""A repository rule exposing the POSIX runfiles library of rules_shell."""

_BUILD = """\
exports_files(
    ["runfiles.sh"],
    visibility = ["//visibility:public"],
)
"""

def _shell_runfiles_repository_impl(repository_ctx):
    # A copy rather than a symlink, so that the file is read the same
    # way on a host without symlink support. Reading it also registers
    # it as something this repository is refetched for.
    repository_ctx.file(
        "runfiles.sh",
        repository_ctx.read(repository_ctx.attr.runfiles),
        executable = False,
    )
    repository_ctx.file("BUILD.bazel", _BUILD)

shell_runfiles_repository = repository_rule(
    doc = "Expose `runfiles.sh` of rules_shell under a public label.",
    implementation = _shell_runfiles_repository_impl,
    attrs = {
        "runfiles": attr.label(
            doc = "The shell runfiles library",
            mandatory = True,
        ),
    },
)
