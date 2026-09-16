"""A repository rule rendering an installed package and its stubs apart.

A distribution that ships no types of its own is typed by a second
distribution named for it with `-stubs` on the end, which is the one
case where the file mypy reads a module out of is not in the same Bazel
target -- or even the same wheel -- as the module itself.

Both halves are rendered under a `site-packages`, because that is the
directory that decides it. A file below one is reached by import and
judged by PEP 561; the same file anywhere else is a source this build
owns, and the stub package's whole meaning is that it is not.

It is rendered twice, because the shape of the package changes what
mypy has to do to find it. `shapes` is an ordinary package: whichever
directory holds its `__init__` is the one answer, and mypy takes it.
`acme` is a namespace package, which no file marks and any number of
directories may contribute to, so mypy has nothing to prefer and
settles for the first directory it is offered by that name -- which
goes wrong as soon as something else in its reach is a directory of the
same name.
"""

_BUILD = """\
load("{defs}", "py_library")

py_library(
    name = "shapes",
    srcs = [
        "site-packages/shapes/__init__.py",
        "site-packages/shapes/core.py",
    ],
    imports = ["site-packages"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "shapes_stubs",
    data = [
        "site-packages/shapes-stubs/__init__.pyi",
        "site-packages/shapes-stubs/core.pyi",
    ],
    imports = ["site-packages"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "acme_gadgets",
    srcs = [
        "site-packages/acme/gadgets/__init__.py",
        "site-packages/acme/gadgets/core.py",
    ],
    imports = ["site-packages"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "acme_gadgets_stubs",
    data = [
        "site-packages/acme-stubs/gadgets/__init__.pyi",
        "site-packages/acme-stubs/gadgets/core.pyi",
    ],
    imports = ["site-packages"],
    visibility = ["//visibility:public"],
)
"""

_INIT = '''\
"""An installed package that ships no types of its own."""
'''

_CORE = '''\
"""The module the stubs describe, as the distribution actually ships it."""


def area(width, height):
    """Return the area of a rectangle."""
    return width * height
'''

_STUB_INIT = '''\
"""Stubs for a package that ships none."""
'''

_STUB_CORE = '''\
"""Stubs for `shapes.core`."""

def area(width: float, height: float) -> float: ...
'''

_GADGETS_INIT = '''\
"""A subpackage of a namespace the distribution does not own outright."""


class Unit:
    """The unit a measurement is given in."""
'''

# `core` imports from the package above it, which is what makes a
# misresolved `acme` reach this far. The package becomes a module with
# an interface the dependency's cache was not written against, so every
# module that named it is re-read from whatever the consumer has --
# which, for a pruned source, is a file with nothing in it.
_GADGETS_CORE = '''\
"""The module the stubs describe, as the distribution actually ships it."""

from acme.gadgets import Unit


def volume(width, height, depth, unit=Unit()):
    """Return the volume of a box."""
    return width * height * depth
'''

_GADGETS_STUB_INIT = '''\
"""Stubs for `acme.gadgets`."""

class Unit: ...
'''

_GADGETS_STUB_CORE = '''\
"""Stubs for `acme.gadgets.core`."""

from acme.gadgets import Unit

def volume(
    width: float, height: float, depth: float, unit: Unit = ...
) -> float: ...
'''

def _stub_example_repository_impl(repository_ctx):
    repository_ctx.file(
        "BUILD.bazel",
        _BUILD.format(defs = str(Label("//python:defs.bzl"))),
    )
    repository_ctx.file("site-packages/shapes/__init__.py", _INIT)
    repository_ctx.file("site-packages/shapes/core.py", _CORE)
    repository_ctx.file("site-packages/shapes-stubs/__init__.pyi", _STUB_INIT)
    repository_ctx.file("site-packages/shapes-stubs/core.pyi", _STUB_CORE)

    # Neither `acme` nor `acme-stubs` gets an `__init__`, which is the
    # whole of what makes the namespace package one. A distribution that
    # shares its top-level name with others cannot claim it, so it ships
    # the subpackage and leaves the name above open.
    repository_ctx.file("site-packages/acme/gadgets/__init__.py", _GADGETS_INIT)
    repository_ctx.file("site-packages/acme/gadgets/core.py", _GADGETS_CORE)
    repository_ctx.file(
        "site-packages/acme-stubs/gadgets/__init__.pyi",
        _GADGETS_STUB_INIT,
    )
    repository_ctx.file(
        "site-packages/acme-stubs/gadgets/core.pyi",
        _GADGETS_STUB_CORE,
    )

stub_example_repository = repository_rule(
    doc = "Render an installed package and a stub distribution for it.",
    implementation = _stub_example_repository_impl,
)
