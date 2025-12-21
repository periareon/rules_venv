"""# py_mypy_aspect"""

load(
    "//python/mypy/private:mypy.bzl",
    _py_mypy_aspect = "py_mypy_aspect",
)

py_mypy_aspect = _py_mypy_aspect
