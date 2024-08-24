"""`rules_venv` exports to match the `rules_python` interface."""

load(
    "@rules_python//python:defs.bzl",
    _PyInfo = "PyInfo",
    _PyRuntimeInfo = "PyRuntimeInfo",
    _py_import = "py_import",
    _py_runtime = "py_runtime",
)
load(
    "//python/venv:defs.bzl",
    "py_venv_binary",
    "py_venv_library",
    "py_venv_test",
)

py_binary = py_venv_binary
py_library = py_venv_library
py_test = py_venv_test

PyInfo = _PyInfo
PyRuntimeInfo = _PyRuntimeInfo
py_import = _py_import
py_runtime = _py_runtime
