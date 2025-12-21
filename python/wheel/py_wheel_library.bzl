"""# py_wheel_library"""

load(
    "//python/wheel/private:wheel.bzl",
    _py_wheel_library = "py_wheel_library",
)

py_wheel_library = _py_wheel_library
