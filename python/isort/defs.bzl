"""# isort

Bazel rules for the Python formatter [isort][is].

### Setup

First ensure `rules_venv` is setup by referring to [rules_venv setup](../index.md#setup).

Next, the `rules_venv` rules work mostly off of toolchains which are used to provide the necessary python targets (aka `isort`)
for the process wrappers. Users will want to make sure they have a way to get the necessary python dependencies. Tools such as
[req-compile](https://github.com/periareon/req-compile) can provide these.

With the appropriate dependencies available, a [py_isort_toolchain](#py_isort_toolchain) will need to be configured:

```python
load("@rules_venv//python/isort:defs.bzl", "py_isort_toolchain")

py_isort_toolchain(
    name = "toolchain_impl",
    isort = "@pip_deps//:isort",
    visibility = ["//visibility:public"]
)

toolchain(
    name = "toolchain",
    toolchain = ":toolchain_impl",
    toolchain_type = "@rules_venv//python/isort:toolchain_type",
    visibility = ["//visibility:public"]
)
```

This toolchain then needs to be registered in the `MODULE.bazel` file.

```python
register_toolchains("//tools/python/isort:toolchain")
```


### Usage

Python code can be formatted using the following command:

```bash
bazel run @rules_venv//python/isort
```

In addition to this formatter, a check can be added to `bazel build` invocations using the [py_isort_aspect](#py_isort_aspect)
aspect. Simply add the following to a `.bazelrc` file to enable this check.

```text
build --aspects=@rules_venv//python/isort:defs.bzl%py_isort_aspect
build --output_groups=+py_isort_checks
```

## Sections and Ordering

Of all isort [sections](https://pycqa.github.io/isort/reference/isort/sections.html), `FIRSTPARTY` and
`THIRDPARTY` follow unique rules to ensure ordering makes sense on a per-target basis.

### First party

- Direct source dependencies passed to the `srcs` attribute.
- Repository relative packages.

### Third party

- Other `py_*` targets (the `deps` attribute). Note that `deps` which use repo absolute import paths
will be considered first party.

## Tips

Isort is sensitive to the [`legacy_create_init`][legacy_init] attribute on python rules. For more correct
and consistent behavior, this value should always be `0` or if the default of `-1` is set, the
[`--incompatible_default_to_explicit_init_py`][incompat_init] flag should be added to the workspace's
`.bazelrc` file to ensure the behavior is disabled.

[legacy_init]: https://bazel.build/reference/be/python#py_binary.legacy_create_init
[incompat_init]: https://github.com/bazelbuild/bazel/issues/10076
[is]: https://pycqa.github.io/isort/
"""

load(
    "//python/isort/private:isort.bzl",
    _py_isort_aspect = "py_isort_aspect",
    _py_isort_test = "py_isort_test",
)
load(
    "//python/isort/private:isort_toolchain.bzl",
    _py_isort_toolchain = "py_isort_toolchain",
)

py_isort_aspect = _py_isort_aspect
py_isort_test = _py_isort_test
py_isort_toolchain = _py_isort_toolchain
