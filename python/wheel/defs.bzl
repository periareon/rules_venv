"""# Wheel

A framework for defining [wheels][whl] from a tree of Bazel targets.

[whl]: https://packaging.python.org/en/latest/specifications/binary-distribution-format/

## Why use this over what `rules_python` provides?

The rules here primarily wrap what rules_python provides but offers some improvements:

1. Requirements are collected from transitive dependencies and added as `Require-Dist` to the wheel.
2. Sources and data are automatically collected.

## Setup

Building wheels requires no setup, however, to activate all features of
the wheel rules, a toolchain must be registered.

First some external python requirements will be required. There is guidance on
how to configure this in projects like [rules_req_compile]( https://github.com/periareon/req-compile).
Once there is a means to fetch external dependencies within your repository, a
toolchain can be defined in a `BUILD.bazel` file.

Example `//:BUILD.bazel`:

```python
load("@rules_venv//python/wheel:defs.bzl", "py_wheel_toolchain")

py_wheel_toolchain(
    name = "py_wheel_toolchain_impl",
    # Definable using bzlmod modules like: https://github.com/periareon/req-compile
    twine = "@pip_deps//twine",
    visibility = ["//visibility:public"],
)

toolchain(
    name = "py_wheel_toolchain",
    toolchain = ":py_wheel_toolchain_impl",
    toolchain_type = "@rules_venv//python/wheel:toolchain_type",
    visibility = ["//visibility:public"],
)
```

Once the toolchain is defined, it should be registered in the `MODULE.bazel` file

Example `//:MODULE.bazel`:

```python
register_toolchains(
    "//:py_wheel_toolchain",
)
```

This will ensure all features of the wheel rules are available and usable.
"""

load(
    ":package_tag.bzl",
    _package_tag = "package_tag",
)
load(
    ":py_wheel_library.bzl",
    _py_wheel_library = "py_wheel_library",
)
load(
    ":py_wheel_publisher.bzl",
    _py_wheel_publisher = "py_wheel_publisher",
)
load(
    ":py_wheel_toolchain.bzl",
    _py_wheel_toolchain = "py_wheel_toolchain",
)

package_tag = _package_tag
py_wheel_library = _py_wheel_library
py_wheel_toolchain = _py_wheel_toolchain
py_wheel_publisher = _py_wheel_publisher
