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
    "//python/venv:py_binary.bzl",
    _py_binary = "py_binary",
)
load(
    "//python/venv:py_library.bzl",
    _py_library = "py_library",
)
load(
    "//python/venv:py_test.bzl",
    _py_test = "py_test",
)
load(
    ":py_executable_info.bzl",
    _PyExecutableInfo = "PyExecutableInfo",
)
load(
    ":py_info.bzl",
    _PyInfo = "PyInfo",
)

py_binary = _py_binary
py_library = _py_library
py_test = _py_test

PyExecutableInfo = _PyExecutableInfo
PyInfo = _PyInfo
PyRuntimeInfo = _PyRuntimeInfo
py_import = _py_import
py_runtime = _py_runtime
