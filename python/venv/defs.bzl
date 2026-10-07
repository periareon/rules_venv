"""# Venv

Core Bazel rules for defining Python targets.

The `py_venv_binary`, `py_venv_library`, `py_venv_test`, and `py_venv_zipapp`
symbols are aliases of `py_binary`, `py_library`, `py_test`, and `py_zipapp`.
"""

load(
    ":py_binary.bzl",
    _py_binary = "py_binary",
)
load(
    ":py_library.bzl",
    _py_library = "py_library",
)
load(
    ":py_test.bzl",
    _py_test = "py_test",
)
load(
    ":py_venv_binary.bzl",
    _py_venv_binary = "py_venv_binary",
)
load(
    ":py_venv_common.bzl",
    _py_venv_common = "py_venv_common",
)
load(
    ":py_venv_library.bzl",
    _py_venv_library = "py_venv_library",
)
load(
    ":py_venv_test.bzl",
    _py_venv_test = "py_venv_test",
)
load(
    ":py_venv_toolchain.bzl",
    _py_venv_toolchain = "py_venv_toolchain",
)
load(
    ":py_venv_zipapp.bzl",
    _py_venv_zipapp = "py_venv_zipapp",
)
load(
    ":py_zipapp.bzl",
    _py_zipapp = "py_zipapp",
)

py_binary = _py_binary
py_zipapp = _py_zipapp
py_library = _py_library
py_test = _py_test

py_venv_binary = _py_venv_binary
py_venv_zipapp = _py_venv_zipapp
py_venv_library = _py_venv_library
py_venv_test = _py_venv_test
py_venv_toolchain = _py_venv_toolchain

py_venv_common = _py_venv_common
