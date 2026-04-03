"""# ty

Bazel rules for the Python type checker [ty][ty].

### Setup

First ensure `rules_venv` is setup by referring to [rules_venv setup](../index.md#setup).

Next, the `ty` rules work mostly off of toolchains which are used to provide the necessary python targets (aka `ty`)
for the process wrappers. Users will want to make sure they have a way to get the necessary python dependencies. Tools such as
[req-compile](https://github.com/periareon/req-compile) can provide these.

With the appropriate dependencies available, a [py_ty_toolchain](#py_ty_toolchain) will need to be configured.
The toolchain accepts either `ty` (a `py_library`, e.g. from pip) or `ty_bin` (an executable); the two are mutually exclusive.

```python
load("@rules_venv//python/ty:defs.bzl", "py_ty_toolchain")

py_ty_toolchain(
    name = "toolchain_impl",
    ty = "@pip_deps//ty",
    visibility = ["//visibility:public"]
)

toolchain(
    name = "toolchain",
    toolchain = ":toolchain_impl",
    toolchain_type = "@rules_venv//python/ty:toolchain_type",
    visibility = ["//visibility:public"]
)
```

This toolchain then needs to be registered in the `MODULE.bazel` file.

```python
register_toolchains("//tools/python/ty:toolchain")
```

From here, [py_ty_test](#py_ty_test) and the [py_ty_aspect](#py_ty_aspect)
should now be usable. Both the test rule and the aspect
use a global flag to determine which ty configuration file to use in actions. The default config is
`//python/ty:ty.toml`; the chosen file must be a valid label (e.g. `ty.toml` or `pyproject.toml`).
Add the following to `.bazelrc` to choose a different configuration file:

```text
build --@rules_venv//python/ty:config=//:ty.toml
```

To use the aspect, you must also enable it and request its output group in `.bazelrc`:

```text
build --aspects=@rules_venv//python/ty:py_ty_aspect.bzl%py_ty_aspect
build --output_groups=+py_ty_checks
```

Test rules can override the config per target via the `config` attribute (they default to the label flag above).


[ty]: https://docs.astral.sh/ty/
"""

load(
    ":py_ty_aspect.bzl",
    _py_ty_aspect = "py_ty_aspect",
)
load(
    ":py_ty_test.bzl",
    _py_ty_test = "py_ty_test",
)
load(
    ":py_ty_toolchain.bzl",
    _py_ty_toolchain = "py_ty_toolchain",
)

py_ty_aspect = _py_ty_aspect
py_ty_test = _py_ty_test
py_ty_toolchain = _py_ty_toolchain
