"""# py_wheel_publisher"""

load(
    "//python/wheel/private:wheel.bzl",
    _py_wheel_publisher = "py_wheel_publisher",
)

py_wheel_publisher = _py_wheel_publisher
