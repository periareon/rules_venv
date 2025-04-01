"""# Pylint

Bazel rules for the Python linter [Pylint][pl].

### Setup

First ensure `rules_venv` is setup by referring to [rules_venv setup](../index.md#setup).

Next, the `pylint` rules work mostly off of toolchains which are used to provide the necessary python targets (aka `pylint`)
for the process wrappers. Users will want to make sure they have a way to get the necessary python dependencies. Tools such as
[req-compile](https://github.com/periareon/req-compile) can provide these.

With the appropriate dependencies available, a [py_pylint_toolchain](#py_pylint_toolchain) will need to be configured:

```python
load("@rules_venv//python/pylint:defs.bzl", "py_pylint_toolchain")

py_pylint_toolchain(
    name = "toolchain_impl",
    pylint = "@pip_deps//:pylint",
    visibility = ["//visibility:public"]
)

toolchain(
    name = "toolchain",
    toolchain = ":toolchain_impl",
    toolchain_type = "@rules_venv//python/pylint:toolchain_type",
    visibility = ["//visibility:public"]
)
```

This toolchain then needs to be registered in the `MODULE.bazel` file.

```python
register_toolchains("//tools/python/pylint:toolchain")
```

From here, [py_pylint_test](#py_pylint_test) and the [py_pylint_aspect](#py_pylint_aspect)
should now be usable. Both of these rules use a global flag to determine which pylint configuration
file to use with in actions. The following snippet can be added to the `.bazelrc` file to chose the
desired configuration file

```text
build --@rules_pylint//python/pylint:config=//:.pylintrc.toml
```

Note that these files will need to be available via [exports_files](https://bazel.build/reference/be/functions#exports_files)


[pl]: https://pylint.pycqa.org/en/latest/
"""

load(
    "//python/pylint/private:pylint.bzl",
    _py_pylint_aspect = "py_pylint_aspect",
    _py_pylint_test = "py_pylint_test",
)
load(
    "//python/pylint/private:pylint_toolchain.bzl",
    _py_pylint_toolchain = "py_pylint_toolchain",
)

py_pylint_aspect = _py_pylint_aspect
py_pylint_test = _py_pylint_test
py_pylint_toolchain = _py_pylint_toolchain
