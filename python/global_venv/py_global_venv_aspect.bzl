"""# py_global_venv_aspect"""

load(
    "//python/global_venv/private:global_venv.bzl",
    _py_global_venv_aspect = "py_global_venv_aspect",
)

py_global_venv_aspect = _py_global_venv_aspect
