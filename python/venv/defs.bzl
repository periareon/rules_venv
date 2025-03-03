"""# Venv

Core Bazel rules for defining Python targets.

"""

load(
    "//python/venv/private:venv.bzl",
    _py_venv_binary = "py_venv_binary",
    _py_venv_library = "py_venv_library",
    _py_venv_test = "py_venv_test",
    _py_venv_zipapp = "py_venv_zipapp",
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
py_venv_zipapp = _py_venv_zipapp
py_venv_library = _py_venv_library
py_venv_test = _py_venv_test
py_venv_toolchain = _py_venv_toolchain

py_global_venv_aspect = _py_global_venv_aspect

py_venv_common = _py_venv_common
