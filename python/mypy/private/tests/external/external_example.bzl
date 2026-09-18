"""A repository rule rendering a typed package into a real external repo.

Everything else in these tests lives in the workspace being built, which
is the one place the naming rules treat specially: a first-party file is
named for the repository root, and that root is only the right answer
because the workspace's own layout is the workspace's to arrange.

A package that arrives from somewhere else is named the other way, by
the packages enclosing it, and there is no way to be standing in that
case without an actual second repository. Rendering one here keeps the
fixture next to the test that reads it and costs nothing to fetch.
"""

_BUILD = """\
load("{defs}", "py_library")

py_library(
    name = "widgets",
    srcs = [
        "widgets/__init__.py",
        "widgets/core.py",
    ],
    imports = ["."],
    visibility = ["//visibility:public"],
)
"""

_INIT = '''\
"""A package installed from elsewhere, with a typed module in it."""
'''

_CORE = '''\
"""A module whose consumers reach past what it publishes.

Its `_tidy` is private by name and imported from outside all the same,
which is what a package's own tests do and what any consumer of these
rules ends up doing sooner or later. There is nothing a re-export can do
about an underscore, so this only resolves if the consumer reaches the
module under the very name it was published as.
"""


def _tidy(text: str) -> str:
    """Put text in the form a widget is labelled with.

    Args:
        text: The text to tidy.

    Returns:
        The tidied text.
    """
    return text.strip().lower()


def label(text: str) -> str:
    """Label a widget.

    Args:
        text: The text to label it with.

    Returns:
        The label.
    """
    return _tidy(text)
'''

def _external_example_repository_impl(repository_ctx):
    repository_ctx.file(
        "BUILD.bazel",
        _BUILD.format(defs = str(Label("//python:defs.bzl"))),
    )
    repository_ctx.file("widgets/__init__.py", _INIT)
    repository_ctx.file("widgets/core.py", _CORE)

external_example_repository = repository_rule(
    doc = "Render a typed package as a repository of its own.",
    implementation = _external_example_repository_impl,
)
