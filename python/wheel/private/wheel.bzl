"""Bazel rules for Python wheels."""

load("@rules_python//python:packaging.bzl", "PyWheelInfo", "py_wheel_rule")
load("//python:defs.bzl", "PyInfo", "py_library")

py_wheel = py_wheel_rule

_TOOLCHAIN_TYPE = str(Label("//python/wheel:toolchain_type"))

_PY_PACKAGE_TAG = "py_package"

def package_tag(name):
    """Generate a tag used to associate the target with a python package.

    This tag should only be applied to other `py_*` targets.

    Example:

    ```python
    load("@rules_venv//python:defs.bzl", "py_library")
    load("@rules_venv//python/wheel:defs.bzl", "package_tag")

    py_library(
        name = "my_target",
        tags = [package_tag("my_python_package")],
        # ...
        # ...
        # ...
    )
    ```

    Args:
        name (str): The name of the package

    Returns:
        str: The tag.
    """
    return "{}={}".format(_PY_PACKAGE_TAG, name)

PyWheelPackageInfo = provider(
    doc = "A provider describing the association of a target with a Python package.",
    fields = {
        "deps": "Depset[Label]: The labels of all direct dependencies to the package and it's submodules.",
        "files": "Depset[File]: A collection of all files (including runfiles) from the target and it's dependencies.",
        "packages": "Depset[str]: The name of all top level packages the current target can opt into. `*` is reserved for all packages.",
    },
)

def _is_dep_from_local_workspace(dep, current_workspace_name):
    if dep.label.workspace_name:
        return False

    if dep.label.workspace_name != current_workspace_name:
        return False

    return True

def _py_wheel_package_aspect_impl(target, ctx):
    if PyWheelPackageInfo in target:
        return []

    package_names = []
    for tag in ctx.rule.attr.tags:
        if tag.startswith(_PY_PACKAGE_TAG):
            _, _, package_name = tag.partition("=")
            package_names.append(package_name)

    if not package_names:
        return []

    deps = []
    transitive_deps = []
    files = [
        target[DefaultInfo].files,
        depset(getattr(ctx.rule.files, "data", [])),
    ]

    for dep in getattr(ctx.rule.attr, "deps", []):
        if PyWheelPackageInfo not in dep:
            # Missing workspace names suggest there's no `workspace(name = "{}")` call in
            # the WORKSPACE file so if this value is empty or it explicitly matches the
            # current workspace name then consider it first party.
            if _is_dep_from_local_workspace(dep, ctx.workspace_name):
                fail(
                    "A workspace local target was found as a dependency but it is not being " +
                    "published with a package (as described by the `package_tag` macro). This " +
                    "would result in a published package that could never resolve dependencies. " +
                    "Please update {}".format(dep.label),
                )

            # External targets not tracked as a submodule are treated as deps.
            deps.append(dep.label.name)
            continue

        # Account for the case where a local package is also published as a wheel.
        if dep.label in package_names:
            deps.append(dep.label)
            continue

        # Any target which has `PyWheelPackageInfo` is expected to be a repo local target.
        dep_info = dep[PyWheelPackageInfo]

        dep_package_names = dep_info.packages.to_list()
        shares_package_tag = "*" in dep_package_names or any([
            pkg in package_names
            for pkg in dep_package_names
        ])

        if not shares_package_tag:
            fail((
                "The dependency {} was found as dependency for packages `{}` but the target isn't " +
                "recorded as a part of any of them. The dependency is currently registered for `{}` " +
                "and will need to be updated (as described by the `package_tag` macro) to be included."
            ).format(dep.label, package_names, dep_package_names))

        transitive_deps.append(dep_info.deps)
        files.append(dep_info.files)

    return [PyWheelPackageInfo(
        packages = depset(package_names),
        files = depset(transitive = files),
        deps = depset(deps, transitive = transitive_deps, order = "topological"),
    )]

py_wheel_package_aspect = aspect(
    doc = "An aspect for collecting info and data from python submodules of a python package.",
    implementation = _py_wheel_package_aspect_impl,
    attr_aspects = ["deps"],
)

def _py_wheel_package_impl(ctx):
    package_info = ctx.attr.package[PyWheelPackageInfo]

    out_requires = ctx.outputs.out_requires
    requires_inputs = []

    requires_args = ctx.actions.args()
    requires_args.add("--output", out_requires)
    requires_args.add_all(package_info.deps, format_each = "--dep=%s", allow_closure = True)
    if ctx.file.constraints_file:
        requires_inputs.append(ctx.file.constraints_file)
        requires_args.add("--constraints_file", ctx.file.constraints_file)

    ctx.actions.run(
        mnemonic = "PyWheelRequire",
        outputs = [out_requires],
        arguments = [requires_args],
        executable = ctx.executable._requires_parser,
        inputs = requires_inputs,
    )

    py_info = ctx.attr.package[PyInfo]

    return [
        PyInfo(
            imports = py_info.imports,
            transitive_sources = py_info.transitive_sources,
        ),
        DefaultInfo(
            files = package_info.files,
            runfiles = ctx.runfiles(transitive_files = package_info.files),
        ),
    ]

py_wheel_package = rule(
    doc = "A rule for collecting all files associated with a Python package.",
    implementation = _py_wheel_package_impl,
    attrs = {
        "constraints_file": attr.label(
            doc = "A file containing python constraints to attach to the detected requirements (`py_library.deps`)",
            allow_single_file = True,
        ),
        "out_requires": attr.output(
            doc = "The output name of the `py_wheel.requires_file` file.",
            mandatory = True,
        ),
        "package": attr.label(
            doc = "The target representing the Python package.",
            providers = [PyInfo],
            mandatory = True,
            aspects = [py_wheel_package_aspect],
        ),
        "_requires_parser": attr.label(
            cfg = "exec",
            executable = True,
            default = Label("//python/wheel/private:requires_parser"),
        ),
    },
)

def _py_wheel_toolchain_impl(ctx):
    toolchain_info = platform_common.ToolchainInfo(
        twine = ctx.attr.twine,
    )
    return [toolchain_info]

py_wheel_toolchain = rule(
    doc = """\
A toolchain for powering the `py_wheel` rules.

```python
load("@rules_venv//python/wheel:defs.bzl", "py_wheel_toolchain")

py_wheel_toolchain(
    name = "py_wheel_toolchain_impl",
    # Definable using bzlmod modules like: https://github.com/periareon/req-compile
    twine = "@pip_deps//:twine",
    visibility = ["//visibility:public"],
)

toolchain(
    name = "py_wheel_toolchain",
    toolchain = ":py_wheel_toolchain_impl",
    toolchain_type = "@rules_venv//python/wheel:toolchain_type",
    visibility = ["//visibility:public"],
)
```
""",
    implementation = _py_wheel_toolchain_impl,
    attrs = {
        "twine": attr.label(
            doc = "A `py_library` for [twine](https://twine.readthedocs.io/en/stable/).",
            providers = [PyInfo],
            mandatory = True,
        ),
    },
)

def _current_py_wheel_toolchain_for_twine_impl(ctx):
    toolchain = ctx.toolchains[_TOOLCHAIN_TYPE]
    if toolchain == None:
        return [PyInfo(
            imports = depset(),
            transitive_sources = depset(),
        )]

    twine = toolchain.twine

    default_info = DefaultInfo(
        files = twine[DefaultInfo].files,
        runfiles = twine[DefaultInfo].default_runfiles,
    )

    return [
        twine[PyInfo],
        default_info,
    ]

current_py_wheel_toolchain_for_twine = rule(
    doc = "A rule for accessing the twine library provided to the current `py_wheel_toolchain`.",
    implementation = _current_py_wheel_toolchain_for_twine_impl,
    toolchains = [
        config_common.toolchain_type(_TOOLCHAIN_TYPE, mandatory = False),
    ],
)

def _rlocationpath(file, workspace_name):
    if file.short_path.startswith("../"):
        return file.short_path[len("../"):]

    return "{}/{}".format(workspace_name, file.short_path)

def _py_wheel_publisher_impl(ctx):
    wheel_info = ctx.attr.wheel[PyWheelInfo]

    args = ctx.actions.args()
    args.set_param_file_format("multiline")
    args.add("--wheel", _rlocationpath(ctx.file.wheel, ctx.workspace_name))
    args.add("--wheel_name_file", _rlocationpath(wheel_info.name_file, ctx.workspace_name))

    if ctx.attr.repository_url:
        args.add("--repository_url", ctx.attr.repository_url)

    args_file = ctx.actions.declare_file("{}.args.txt".format(ctx.label.name))
    ctx.actions.write(
        output = args_file,
        content = args,
    )

    twine = ctx.executable._twine_process_wrapper
    extension = twine.extension
    executable = ctx.actions.declare_file("{}.{}".format(ctx.label.name, extension).rstrip("."))

    ctx.actions.symlink(
        output = executable,
        target_file = twine,
        is_executable = True,
    )

    return [
        DefaultInfo(
            files = depset([executable]),
            runfiles = ctx.runfiles([args_file, ctx.file.wheel, wheel_info.name_file]).merge(
                ctx.attr._twine_process_wrapper[DefaultInfo].default_runfiles,
            ),
            executable = executable,
        ),
        RunEnvironmentInfo(
            environment = {
                "RULES_VENV_WHEEL_PUBLISHER_ARGS": _rlocationpath(args_file, ctx.workspace_name),
            },
        ),
    ]

py_wheel_publisher = rule(
    doc = """\
A rule for publishing wheels to pypi registries.

The rule uses [twine][tw] to python registries. Users should refer to the documentation there
for any configuration flags (such as auth) needed to deploy to the desired location.

[tw]: https://twine.readthedocs.io/en/stable/index.html#twine
""",
    implementation = _py_wheel_publisher_impl,
    attrs = {
        "repository_url": attr.string(
            doc = "The repository (package index) URL to upload the wheel to. If passed the `twine` arg `--repository-url` will be set to this value.",
        ),
        "wheel": attr.label(
            mandatory = True,
            allow_single_file = True,
            doc = "The wheel to extract.",
        ),
        "_twine_process_wrapper": attr.label(
            cfg = "exec",
            executable = True,
            default = Label("//python/wheel/private:twine_process_wrapper"),
        ),
    },
    executable = True,
)

def py_wheel_library(
        name,
        srcs = [],
        deps = [],
        data = [],
        abi = None,
        author = None,
        author_email = None,
        classifiers = None,
        constraints_file = None,
        data_files = None,
        description_content_type = None,
        description_file = None,
        extra_distinfo_files = None,
        homepage = None,
        license = None,
        platform = None,
        project_urls = None,
        python_requires = None,
        python_tag = None,
        strip_path_prefixes = None,
        summary = None,
        version = "0.0.0",
        distribution = None,
        repository_url = None,
        **kwargs):
    """Define a `py_library` with an associated wheel.

    This rule will traverse dependencies (`deps`) to collect all data and dependencies
    that belong to the current package. Any dependency tagged with the `package_tag` whose
    name matches this targets name will be considered a submodule and included in the package.

    Example:

    ```python
    load("@rules_venv//python:defs.bzl", "py_library")
    load("@rules_venv//python/wheel:defs.bzl", "package_tag", "py_wheel_library")

    py_library(
        name = "submodule",
        srcs = ["submodule.py"],
        tags = [
            # Note this name matches the name of the `py_wheel_library` target
            # and as a result will be included as a submodule within the wheel.
            package_tag("my_py_package")
        ],
    )

    py_wheel_library(
        name = "my_py_package",
        deps = [":submodule"],
    )
    ```

    Targets created by this library:

    | name | details |
    | --- | --- |
    | `{name}` | The `py_library` target for the wheel. |
    | `{name}.whl` | The `py_wheel` target created from the `{name}` target. |
    | `{name}.publish` | A [`py_wheel_publisher`](#py_wheel_publisher) target for publishing the wheel to a remote index. Defined only with `repository_url`. |

    Args:
        name (str): The name of the target.
        srcs (list): Python source files which make up the lirary.
        deps (list): A list of Python dependencies.
        data (list): Data required at runtime.
        abi (str): Python ABI tag. 'none' for pure-Python wheels.
        author_email (str): A string specifying the email address of the package author.
        author (str): A string specifying the author of the package.
        classifiers (list): A list of strings describing the categories for the
            package. For valid classifiers see https://pypi.org/classifiers
        constraints_file (Label): A constraints (`requirements.in`) file which contains package constraints.
        data_files (list): "Any file that is not normally installed inside site-packages
            goes into the .data directory, named as the .dist-info directory but with the
            `.data/` extension. Allowed paths: `("purelib", "platlib", "headers", "scripts", "data")`
        description_content_type (str): The type of contents in description_file. If not
            provided, the type will be inferred from the extension of description_file. Also
            see https://packaging.python.org/en/latest/specifications/core-metadata/#description-content-type
        description_file (Label): A file containing text describing the package.
        extra_distinfo_files (list): Extra files to add to distinfo directory in the archive.
        homepage (str): A string specifying the URL for the package homepage.
        license (str): A string specifying the license of the package.
        platform (str): Supported platform. Use 'any' for pure-Python wheel.
        project_urls (list): A string dict specifying additional browsable URLs for the project
            and corresponding labels, where label is the key and url is the value. e.g
            `{{"Bug Tracker": "http://bitbucket.org/tarek/distribute/issues/"}}`
        python_requires (str): Python versions required by this distribution, e.g. '>=3.9,<3.13'
        python_tag (str): Supported Python version(s), eg `py3`, `cp39.cp310`, etc
        strip_path_prefixes (list): path prefixes to strip from files added to the generated package
        summary (str): A one-line summary of what the distribution does
        version (str): The version of the package.
        distribution (str): Name of the distribution. If unset, `name` will be used.
        repository_url (str): The repository (package index) URL to upload the wheel to.
        **kwargs: Additional keyword arguments.
    """

    tags = kwargs.pop("tags", [])
    manual_tags = depset(tags + ["manual"]).to_list()
    visibility = kwargs.pop("visibility", None)

    py_library(
        name = name,
        srcs = srcs,
        data = data,
        deps = deps,
        tags = tags + [package_tag(name)],
        visibility = visibility,
        **kwargs
    )

    requires_file = "{}.requires.txt".format(name)
    package_name = "{}.package".format(name)
    py_wheel_package(
        name = package_name,
        constraints_file = constraints_file,
        out_requires = requires_file,
        package = name,
        tags = manual_tags,
        visibility = ["//visibility:private"],
        **kwargs
    )

    if distribution == None:
        distribution = name

    wheel_name = "{}.whl".format(name)
    py_wheel(
        name = wheel_name,
        distribution = distribution,
        python_tag = python_tag,
        requires_file = requires_file,
        version = version,
        abi = abi,
        platform = platform,
        deps = [package_name],
        author = author,
        author_email = author_email,
        classifiers = classifiers,
        data_files = data_files,
        description_content_type = description_content_type,
        description_file = description_file,
        extra_distinfo_files = extra_distinfo_files,
        homepage = homepage,
        license = license,
        project_urls = project_urls,
        python_requires = python_requires,
        strip_path_prefixes = strip_path_prefixes,
        summary = summary,
        tags = manual_tags,
        visibility = visibility,
        **kwargs
    )

    if repository_url != None:
        py_wheel_publisher(
            name = "{}.publish".format(name),
            wheel = wheel_name,
            repository_url = repository_url,
            tags = manual_tags,
            visibility = ["//visibility:private"],
            **kwargs
        )
