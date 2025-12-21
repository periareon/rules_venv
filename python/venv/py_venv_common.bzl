"""# py_venv_common"""

load(
    "//python/venv/private:venv_common.bzl",
    _py_venv_common = "py_venv_common",
)

py_venv_common = _py_venv_common
