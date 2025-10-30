"""# Pex

Bazel rules for the Python executable packaging tool [pex][pex].

### Setup

First ensure `rules_venv` is setup by referring to [rules_venv setup](../index.md#setup).

Next, the `pex` rules work mostly off of toolchains which are used to provide the necessary python targets (aka `pex`)
for the process wrappers. Users will want to make sure they have a way to get the necessary python dependencies. Tools such as
[req-compile](https://github.com/periareon/req-compile) can provide these.

With the appropriate dependencies available, a [py_pex_toolchain](#py_pex_toolchain) will need to be configured:

```python
load("@rules_venv//python/pex:defs.bzl", "py_pex_toolchain")

py_pex_toolchain(
    name = "toolchain_impl",
    pex = "@pip_deps//:pex",
    visibility = ["//visibility:public"]
)

toolchain(
    name = "toolchain",
    toolchain = ":toolchain_impl",
    toolchain_type = "@rules_venv//python/pex:toolchain_type",
    visibility = ["//visibility:public"]
)
```

This toolchain then needs to be registered in the `MODULE.bazel` file.

```python
register_toolchains("//tools/python/pex:toolchain")
```


### Usage

Python executables can be packaged using the following command:

```bash
bazel run @rules_venv//python/pex
```

[pex]: https://github.com/pantsbuild/pex
"""

load(
    "//python/pex/private:pex.bzl",
    _py_pex_binary = "py_pex_binary",
    _py_scie_binary = "py_scie_binary",
)
load(
    "//python/pex/private:pex_toolchain.bzl",
    _py_pex_toolchain = "py_pex_toolchain",
)

py_pex_binary = _py_pex_binary
py_scie_binary = _py_scie_binary
py_pex_toolchain = _py_pex_toolchain
