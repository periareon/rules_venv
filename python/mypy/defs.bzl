"""# rules_mypy

Bazel rules for the Python linter [mypy][mp].

### Setup

First ensure `rules_venv` is setup by referring to [rules_venv setup](../index.md#setup).

Next, the `mypy` rules work mostly off of toolchains which are used to provide the necessary python targets (aka `mypy`)
for the process wrappers. Users will want to make sure they have a way to get the necessary python dependencies. Tools such as
[req-compile](https://github.com/periareon/req-compile) can provide these.

With the appropriate dependencies available, a [py_mypy_toolchain](#py_mypy_toolchain) will need to be configured:

```python
load("@rules_venv//python:defs.bzl", "py_library")
load("@rules_venv//python/mypy:defs.bzl", "py_mypy_toolchain")

py_library(
    name = "mypy_deps",
    deps = [
        "@pip_deps//mypy",

        # Types libraries can also be added here.
    ],
)

py_mypy_toolchain(
    name = "toolchain_impl",
    mypy = ":mypy_deps",
    visibility = ["//visibility:public"]
)

toolchain(
    name = "toolchain",
    toolchain = ":toolchain_impl",
    toolchain_type = "@rules_venv//python/mypy:toolchain_type",
    visibility = ["//visibility:public"]
)
```

This toolchain then needs to be registered in the `MODULE.bazel` file.

```python
register_toolchains("//tools/python/mypy:toolchain")
```

From here, [py_mypy_test](#py_mypy_test) and the [py_mypy_aspect](#py_mypy_aspect)
should now be usable. Both of these rules use a global flag to determine which mypy configuration
file to use with in actions. The following snippet can be added to the `.bazelrc` file to chose the
desired configuration file

```text
build --@rules_mypy//python/mypy:config=//:.mypyrc.toml
```

Note that these files will need to be available via [exports_files](https://bazel.build/reference/be/functions#exports_files)


[mp]: https://mypy.readthedocs.io/
"""

load(
    ":py_mypy_aspect.bzl",
    _py_mypy_aspect = "py_mypy_aspect",
)
load(
    ":py_mypy_test.bzl",
    _py_mypy_test = "py_mypy_test",
)
load(
    ":py_mypy_toolchain.bzl",
    _py_mypy_toolchain = "py_mypy_toolchain",
)

py_mypy_aspect = _py_mypy_aspect
py_mypy_test = _py_mypy_test
py_mypy_toolchain = _py_mypy_toolchain
