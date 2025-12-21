"""# py_wheel_toolchain"""

load(
    "//python/wheel/private:wheel.bzl",
    _py_wheel_toolchain = "py_wheel_toolchain",
)

py_wheel_toolchain = _py_wheel_toolchain
