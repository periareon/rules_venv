"""# py_global_venv"""

load(
    "//python/global_venv/private:global_venv.bzl",
    _py_global_venv = "py_global_venv",
)

py_global_venv = _py_global_venv
