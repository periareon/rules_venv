"""# py_zipapp"""

load(
    "//python/venv/private:venv_zipapp.bzl",
    _py_zipapp = "py_zipapp",
)

py_zipapp = _py_zipapp
