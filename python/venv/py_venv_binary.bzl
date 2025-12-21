"""# py_venv_binary"""

load(
    "//python/venv/private:venv.bzl",
    _py_venv_binary = "py_venv_binary",
)

py_venv_binary = _py_venv_binary
