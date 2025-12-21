"""# py_venv_toolchain"""

load(
    "//python/venv/private:venv_toolchain.bzl",
    _py_venv_toolchain = "py_venv_toolchain",
)

py_venv_toolchain = _py_venv_toolchain
