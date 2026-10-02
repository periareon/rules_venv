# rules_venv

This repository implements Bazel rules for [Python](https://www.python.org/) and is designed to be a drop-in
replacement for the existing [rules_python](https://github.com/bazelbuild/rules_python) where uses of
`@rules_python//python:defs.bzl` can be replaced with `@rules_venv//python:defs.bzl`.

## Improvements over `rules_python`

While `rules_python` has fantastic toolchain infrastructure which this repo relies on, `rules_python` ultimately
suffers from a few issues which this repo aims to solve:

1. Use of `PYTHONPATH` to construct the python environment leads to operating system limitations.

    Some details on `MAX_ARG_STRLEN` and `ARG_MAX` can be found here: <https://unix.stackexchange.com/a/120842>

2. Slow startup on windows systems that do not support symlinks.

    `rules_python` creates zipapps on systems that do not support runfiles. For large projects, this can lead to
    large (~500MB+) zip files being constantly compressed and uncompressed to run simple actions which is a lot
    more expensive than systems which support runfiles.

## Setup

```python
bazel_dep(name = "rules_venv", version = "{version}")
```

## Environment variables

### `RULES_VENV_EXTRACT_ROOT`

By default each launch of a `py_venv_binary` or `py_venv_test` builds its venv in a temporary directory that is
deleted on exit, so `sys.executable` is only valid while the process runs. When this variable is set, the venv
is instead built at `$RULES_VENV_EXTRACT_ROOT/<repo>/<package>/<name>.venv` (with `_main` for the main
repository) and, on platforms without runfiles support, the rendered runfiles tree beside it as `<name>.runfiles`.
Both are left in place and reused by later launches of the same target unless the interpreter, import paths, or
runfiles collection have changed. Cleaning up the root is the responsibility of the caller. A relative path is
resolved against the working directory.

### `RULES_PYTHON_EXTRACT_ROOT`

Honored like `RULES_VENV_EXTRACT_ROOT` so a root configured for `rules_python` is shared, but
`RULES_VENV_EXTRACT_ROOT` takes priority when both are set.
