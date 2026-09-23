"""Repository rules rendering third party Python under a private name."""

# The directory the wheels are unpacked under, and so the package they
# are imported through. A venv puts a repository's *root* on `sys.path`,
# under a canonical name Bazel mangles (`+vendor+...`), so what is
# importable is the directory inside it -- written below, not named by
# any label. `python.runfiles` reaches rules_python's runfiles library
# the same way, and is likewise no statement about that repository's
# name.
#
# The name is a top level one, because a `sys.path` root is where the
# venv looks, and one no distribution installs.
_VENDOR = "rules_venv_vendor"

# The repository a single wheel lands in. One per wheel, each unpacking
# into the same `_VENDOR` directory, so a package is fetched only when
# something depends on it.
#
# That works because nothing writes an `__init__.py` for `_VENDOR`: it
# is a namespace package, which any number of `sys.path` roots may
# contribute to and Python merges. A directory with an `__init__.py` is
# the opposite -- the first root holding one answers for the name and
# the rest become unreachable -- so the file that is not written here is
# what lets there be more than one of these repositories.
_REPOSITORY = "rules_venv_wheel_{module}"

# Where PyPI serves a wheel from, given its coordinates. This is the
# redirect form of the path rather than the hashed one a project page
# shows, so that the version is the only thing a bump has to touch
# besides the checksum.
#
# A wheel's file name spells the distribution the way a module does,
# with `-` escaped to `_`, and the directory it sits in accepts that
# spelling too. So a package's module name is the whole of its
# coordinates here, and a distribution published as `tomli-w` is written
# below the one way it is ever read.
_PYPI_URL = "https://files.pythonhosted.org/packages/py3/{initial}/{module}/{module}-{version}-py3-none-any.whl"

# The wheels vendored here. Adding one is an entry in this list and a
# name in the root module's `use_repo`. A wheel is only a candidate if
# it is `py3-none-any` and reaches its own modules by plain imports,
# which is what lets it be read under a name it does not install as.
_PACKAGES = [
    # The TOML writer the linter rules regenerate their configs with.
    struct(
        module = "tomli_w",
        sha256 = "188306098d013b691fcadc011abd66727d3c414c571bb01b1a174ba8c983cf90",
        version = "1.2.0",
    ),
]

# How deep a distribution's directories are walked looking for sources.
# Starlark has no recursion and no `while`, so the walk is a bounded
# number of passes. No wheel vendored here is near this deep.
_MAX_DEPTH = 16

_BUILD = """\
load("{defs}", "py_library")

# A distribution as its wheel ships it, moved under a namespace package
# these rules own and otherwise unchanged apart from the imports it
# makes of itself. The license it ships travels with it.
py_library(
    name = "{module}",
    srcs = glob(["{vendor}/{module}/**/*.py"]),
    data = glob(
        [
            "{vendor}/{module}/**/*.pyi",
            "{vendor}/{module}/**/py.typed",
            "{vendor}/*.dist-info/LICENSE*",
        ],
        allow_empty = True,
    ),
    visibility = ["//visibility:public"],
)
"""

def _python_sources(repository_ctx, root):
    """Find every Python source under a directory.

    Args:
        repository_ctx (repository_ctx): The repository rule's context.
        root (str): The directory to walk, relative to the repository.

    Returns:
        list: The sources found, as repository relative paths.
    """
    sources = []
    pending = [root]

    for _ in range(_MAX_DEPTH):
        if not pending:
            break

        current = pending
        pending = []
        for directory in current:
            for entry in repository_ctx.path(directory).readdir():
                child = "{}/{}".format(directory, entry.basename)
                if entry.is_dir:
                    pending.append(child)
                elif child.endswith(".py"):
                    sources.append(child)

    if pending:
        fail("'{}' nests deeper than {} directories.".format(root, _MAX_DEPTH))

    return sources

def _relocate(repository_ctx, module, sources):
    """Point a distribution's imports of itself at the vendored name.

    A distribution reaches its own modules by the name it installs
    under, which is not the name it is read through here. Rewriting
    those is the whole cost of relocating, and it is only cheap because
    the names are spelled the same few ways -- which is the bar for
    vendoring a distribution rather than depending on it.

    A wheel that clears that bar is a property of the wheel, not
    something this can assume, so every import left naming the module
    afterwards is a `fail` rather than a module that quietly resolves
    against whatever else the venv has on `sys.path`.

    Args:
        repository_ctx (repository_ctx): The repository rule's context.
        module (str): The top level module the distribution installs.
        sources (list): The distribution's sources, as returned by
            `_python_sources`.
    """
    replacements = [
        ("from {}.".format(module), "from {}.{}.".format(_VENDOR, module)),
        ("from {} import".format(module), "from {}.{} import".format(_VENDOR, module)),
        ("import {}.".format(module), "import {}.{}.".format(_VENDOR, module)),
    ]

    for source in sources:
        content = repository_ctx.read(source)

        rewritten = content
        for old, new in replacements:
            rewritten = rewritten.replace(old, new)

        if rewritten != content:
            repository_ctx.file(source, rewritten, executable = False)

        for number, line in enumerate(rewritten.split("\n")):
            if _imports_module(line.strip(), module):
                fail("{}:{}: cannot relocate '{}'.".format(source, number + 1, line.strip()))

def _imports_module(line, module):
    """Whether a line is an import statement still naming a module.

    Args:
        line (str): A line of Python, stripped of its indentation.
        module (str): The top level module the distribution installs.

    Returns:
        bool: Whether the line reaches `module` by its installed name.
    """
    for keyword in ("import ", "from "):
        if not line.startswith(keyword + module):
            continue

        # `import tomli_w_x` names a different module than `tomli_w`,
        # and only what follows the name says which this is.
        tail = line[len(keyword) + len(module):]
        return not tail or tail[0] in " ,."

    return False

def _vendor_repository_impl(repository_ctx):
    module = repository_ctx.attr.module

    # Unpacked into the vendor directory rather than the repository
    # root, which is the whole of making it importable under that name:
    # the venv puts the root on `sys.path`, so a wheel that would have
    # installed `{module}` is read as `{vendor}.{module}` instead.
    #
    # It leaves the `.dist-info` beside the package. That is not
    # importable -- no directory with a `.` or a `-` in it is -- and the
    # BUILD file names only the license out of it.
    repository_ctx.download_and_extract(
        url = repository_ctx.attr.url,
        sha256 = repository_ctx.attr.sha256,
        type = "zip",
        output = _VENDOR,
    )

    root = "{}/{}".format(_VENDOR, module)
    if not repository_ctx.path(root).exists:
        fail("'{}' installs no top level '{}'.".format(repository_ctx.attr.url, module))

    _relocate(repository_ctx, module, _python_sources(repository_ctx, root))

    repository_ctx.file("BUILD.bazel", _BUILD.format(
        defs = str(Label("//python:defs.bzl")),
        module = module,
        vendor = _VENDOR,
    ))

_vendor_repository = repository_rule(
    doc = "Render one wheel under a name these rules own.",
    implementation = _vendor_repository_impl,
    attrs = {
        "module": attr.string(
            doc = "The top level module the wheel installs.",
            mandatory = True,
        ),
        "sha256": attr.string(
            doc = "The expected checksum of the wheel.",
            mandatory = True,
        ),
        "url": attr.string(
            doc = "Where the wheel is fetched from.",
            mandatory = True,
        ),
    },
)

def _vendor_impl(module_ctx):
    # No tags: what is vendored is these rules' own business, so the
    # list lives beside the code that renders it and a consumer's
    # `MODULE.bazel` says nothing but the repository names.
    for package in _PACKAGES:
        _vendor_repository(
            name = _REPOSITORY.format(module = package.module),
            module = package.module,
            sha256 = package.sha256,
            url = _PYPI_URL.format(
                initial = package.module[0],
                module = package.module,
                version = package.version,
            ),
        )

    # Every repository above is a checksummed download of a fixed
    # version, and nothing here reads the host, the environment, or a
    # tag. The same Bazel therefore produces the same repositories
    # anywhere, so a lock file has nothing to add and consumers of these
    # rules do not carry an entry for this extension in theirs.
    return module_ctx.extension_metadata(reproducible = True)

vendor = module_extension(
    doc = """\
Third party Python the rules themselves need.

A ruleset cannot reach for the consumer's own packages, so the few its
runners need are fetched here, one repository to a wheel. Each is
rendered under `{vendor}` rather than the top level name it installs to:
a linter action puts the runner and the target it is checking in one
venv, so a package of these rules' would sit on the same `sys.path` as a
package of the target's by the same name, and one would quietly shadow
the other. It is what pip does with its own vendored packages.

`{vendor}` is a namespace package, which is what lets every repository
put its wheel in a directory of that name and have them all be reachable
at once.
""".format(vendor = _VENDOR),
    implementation = _vendor_impl,
)
