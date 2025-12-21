"""`rules_venv` exports to match the `rules_python` interface."""

load(
    "@rules_python//python:py_import.bzl",
    _py_import = "py_import",
)
load(
    "@rules_python//python:py_runtime.bzl",
    _py_runtime = "py_runtime",
)
load(
    "@rules_python//python:py_runtime_info.bzl",
    _PyRuntimeInfo = "PyRuntimeInfo",
)
load(
    "//python/venv:py_venv_binary.bzl",
    "py_venv_binary",
)
load(
    "//python/venv:py_venv_library.bzl",
    "py_venv_library",
)
load(
    "//python/venv:py_venv_test.bzl",
    "py_venv_test",
)
load(
    ":py_info.bzl",
    _PyInfo = "PyInfo",
)

py_binary = py_venv_binary
py_library = py_venv_library
py_test = py_venv_test

PyInfo = _PyInfo
PyRuntimeInfo = _PyRuntimeInfo
py_import = _py_import
py_runtime = _py_runtime
