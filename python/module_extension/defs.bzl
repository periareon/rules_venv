"""# Module Extensions

Rules for building [Module Extensions](https://docs.python.org/3/extending/extending.html)
"""

load(
    "//python/module_extension/private:cc_extension.bzl",
    _py_cc_extension = "py_cc_extension",
)

py_cc_extension = _py_cc_extension
