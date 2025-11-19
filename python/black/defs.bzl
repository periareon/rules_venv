"""# Black

Bazel rules for the Python formatter [black][blk].

### Setup

First ensure `rules_venv` is setup by referring to [rules_venv setup](../index.md#setup).

Next, the `black` rules work mostly off of toolchains which are used to provide the necessary python targets (aka `black`)
for the process wrappers. Users will want to make sure they have a way to get the necessary python dependencies. Tools such as
[req-compile](https://github.com/periareon/req-compile) can provide these.

With the appropriate dependencies available, a [py_black_toolchain](#py_black_toolchain) will need to be configured:

```python
load("@rules_venv//python/black:defs.bzl", "py_black_toolchain")

py_black_toolchain(
    name = "toolchain_impl",
    black = "@pip_deps//black",
    visibility = ["//visibility:public"]
)

toolchain(
    name = "toolchain",
    toolchain = ":toolchain_impl",
    toolchain_type = "@rules_venv//python/black:toolchain_type",
    visibility = ["//visibility:public"]
)
```

This toolchain then needs to be registered in the `MODULE.bazel` file.

```python
register_toolchains("//tools/python/black:toolchain")
```


### Usage

Python code can be formatted using the following command:

```bash
bazel run @rules_venv//python/black
```

In addition to this formatter, a check can be added to `bazel build` invocations using the [py_black_aspect](#py_black_aspect)
aspect. Simply add the following to a `.bazelrc` file to enable this check.

```text
build --aspects=@rules_venv//python/black:defs.bzl%py_black_aspect
build --output_groups=+py_black_checks
```

[blk]: https://black.readthedocs.io/en/stable/index.html
"""

load(
    "//python/black/private:black.bzl",
    _py_black_aspect = "py_black_aspect",
    _py_black_test = "py_black_test",
)
load(
    "//python/black/private:black_toolchain.bzl",
    _py_black_toolchain = "py_black_toolchain",
)

py_black_aspect = _py_black_aspect
py_black_test = _py_black_test
py_black_toolchain = _py_black_toolchain
