# rules_venv

## Overview

This repository implements Bazel rules for Python and is designed to be a drop-in replacement for the existing
[rules_python](https://github.com/bazelbuild/rules_python) where uses of `@rules_python//python:defs.bzl` can
be replaced with `@rules_venv//python:defs.bzl`.

### Improvements over `rules_python`

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
