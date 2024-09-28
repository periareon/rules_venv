"""# rules_venv

## Overview

This repository implements Bazel rules for Python and is designed to be a drop-in replacement for the existing
[rules_python](https://github.com/bazelbuild/rules_python) where uses of `@rules_python//python:defs.bzl` can
be replaced with `@rules_venv//python:defs.bzl`.

### Improvements over `rules_python`

While `rules_python` has fantastic toolchain infrastructure which this repo relies on, `rules_python` ultimately
suffers from a few issues which this repo aims to solve:

1. Use of `PYTHONPATH` to construct the python environment leads to operating system limitations.

    Some details on `MAX_ARG_STRLEN` and `ARG_MAX` can be found here: https://unix.stackexchange.com/a/120842

2. Slow startup on windows systems that do not support symlinks.

    `rules_python` creates zipapps on systems that do not support runfiles. For large projects, this can lead to
    large (~500MB+) zip files being constantly compressed and uncompressed to run simple actions which is a lot
    more expensive than systems which support runfiles.

## Setup

### WORKSPACE.bazel

```starlark
load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# See releases for urls and checksums
http_archive(
    name = "rules_venv",
    sha256 = "{sha256}",
    urls = ["https://github.com/periareon/rules_venv/releases/download/{version}/rules_venv-v{version}.tar.gz"],
)

load("@rules_venv//venv:repositories.bzl", "venv_register_toolchains", "rules_venv_dependencies")

rules_venv_dependencies()

venv_register_toolchains()

load("@rules_venv//python/venv:repositories_transitive.bzl", "rules_venv_transitive_deps")

rules_venv_transitive_deps()
```

### bzlmod

```starlark
bazel_dep(name = "rules_venv", version = "{version}")
```

## `py_venv_common`

An experimental API for creating python executables within user author rules.

- [create_dep_info](#create_dep_info)
- [create_py_info](#create_py_info)
- [create_python_zip_file](#create_python_zip_file)
- [create_runfiles_collection](#create_runfiles_collection)
- [create_venv_attrs](#create_venv_attrs)
- [create_venv_entrypoint](#create_venv_entrypoint)
- [get_toolchain](#get_toolchain)

## Rules

- [py_venv_binary](#py_venv_binary)
- [py_venv_library](#py_venv_library)
- [py_venv_test](#py_venv_test)
- [py_venv_toolchain](#py_venv_toolchain)

---
---
"""

load(
    "//python/venv/private:venv.bzl",
    _py_venv_binary = "py_venv_binary",
    _py_venv_library = "py_venv_library",
    _py_venv_test = "py_venv_test",
)
load(
    "//python/venv/private:venv_common.bzl",
    _py_venv_common = "py_venv_common",
)
load(
    "//python/venv/private:venv_global.bzl",
    _py_global_venv_aspect = "py_global_venv_aspect",
)
load(
    "//python/venv/private:venv_toolchain.bzl",
    _py_venv_toolchain = "py_venv_toolchain",
)

py_venv_binary = _py_venv_binary
py_venv_library = _py_venv_library
py_venv_test = _py_venv_test
py_venv_toolchain = _py_venv_toolchain

py_global_venv_aspect = _py_global_venv_aspect

py_venv_common = _py_venv_common
