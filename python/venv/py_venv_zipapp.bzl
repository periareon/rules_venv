"""# py_venv_zipapp"""

load(
    "//python/venv/private:venv_zipapp.bzl",
    _py_venv_zipapp = "py_venv_zipapp",
)

py_venv_zipapp = _py_venv_zipapp
