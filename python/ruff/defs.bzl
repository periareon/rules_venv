"""# ruff

Bazel rules for the Python linter [ruff][rf].

### Setup

First ensure `rules_venv` is setup by referring to [rules_venv setup](../index.md#setup).

Next, the `ruff` rules work mostly off of toolchains which are used to provide the necessary python targets (aka `ruff`)
for the process wrappers. Users will want to make sure they have a way to get the necessary python dependencies. Tools such as
[req-compile](https://github.com/periareon/req-compile) can provide these.

With the appropriate dependencies available, a [py_ruff_toolchain](#py_ruff_toolchain) will need to be configured.
The toolchain accepts either `ruff` (a `py_library`, e.g. from pip) or `ruff_bin` (an executable); the two are mutually exclusive.

```python
load("@rules_venv//python/ruff:defs.bzl", "py_ruff_toolchain")

py_ruff_toolchain(
    name = "toolchain_impl",
    ruff = "@pip_deps//ruff",
    visibility = ["//visibility:public"]
)

toolchain(
    name = "toolchain",
    toolchain = ":toolchain_impl",
    toolchain_type = "@rules_venv//python/ruff:toolchain_type",
    visibility = ["//visibility:public"]
)
```

This toolchain then needs to be registered in the `MODULE.bazel` file.

```python
register_toolchains("//tools/python/ruff:toolchain")
```

From here, [py_ruff_test](#py_ruff_test) and the [py_ruff_aspect](#py_ruff_aspect)
should now be usable. [py_ruff_test](#py_ruff_test) is a convenience that creates a test suite running both
[py_ruff_check_test](#py_ruff_check_test) and [py_ruff_format_test](#py_ruff_format_test). Both the test rules and the aspect
use a global flag to determine which ruff configuration file to use in actions. The default config is
`//python/ruff:ruff.toml`; the chosen file must be a valid label (e.g. `ruff.toml` or `pyproject.toml`).
Add the following to `.bazelrc` to choose a different configuration file:

```text
build --@rules_venv//python/ruff:config=//:.ruffrc.toml
```

To use the aspect, you must also enable it and request its output group in `.bazelrc`:

```text
build --aspects=@rules_venv//python/ruff:py_ruff_aspect.bzl%py_ruff_aspect
build --output_groups=+py_ruff_checks
```

Test rules can override the config per target via the `config` attribute (they default to the label flag above).


### Usage

Python code can be formatted using:

```bash
bazel run @rules_venv//python/ruff:format
```

Lint issues that support auto-fix can be applied using:

```bash
bazel run @rules_venv//python/ruff:fix
```

Both commands accept optional Bazel scope arguments (e.g. `//...` or `//some/package:all`); the default is `//...:all`.


[rf]: https://docs.astral.sh/ruff/
"""

load(
    ":py_ruff_aspect.bzl",
    _py_ruff_aspect = "py_ruff_aspect",
)
load(
    ":py_ruff_check_test.bzl",
    _py_ruff_check_test = "py_ruff_check_test",
)
load(
    ":py_ruff_format_test.bzl",
    _py_ruff_format_test = "py_ruff_format_test",
)
load(
    ":py_ruff_test.bzl",
    _py_ruff_test = "py_ruff_test",
)
load(
    ":py_ruff_toolchain.bzl",
    _py_ruff_toolchain = "py_ruff_toolchain",
)

py_ruff_aspect = _py_ruff_aspect
py_ruff_test = _py_ruff_test
py_ruff_format_test = _py_ruff_format_test
py_ruff_check_test = _py_ruff_check_test
py_ruff_toolchain = _py_ruff_toolchain
