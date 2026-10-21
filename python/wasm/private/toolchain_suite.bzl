"""A `py_wasm_toolchain` together with its `toolchain` registration target.

The `py_wasm` extension writes a repository whose BUILD file calls this once
per supported Python version and host; `register_toolchains("@<hub>//:all")`
then registers them all, and resolution picks by host and, through rules_python's
`is_python_X.Y`, by the Python version a module builds for.
"""

load("//python/wasm:py_wasm_toolchain.bzl", "py_wasm_toolchain")

_CONSTRAINTS = {
    "linux-aarch64": [
        Label("@platforms//os:linux"),
        Label("@platforms//cpu:aarch64"),
    ],
    "linux-x86_64": [
        Label("@platforms//os:linux"),
        Label("@platforms//cpu:x86_64"),
    ],
    "macos-aarch64": [
        Label("@platforms//os:macos"),
        Label("@platforms//cpu:aarch64"),
    ],
    "macos-x86_64": [
        Label("@platforms//os:macos"),
        Label("@platforms//cpu:x86_64"),
    ],
}

SUPPORTED_HOSTS = _CONSTRAINTS.keys()

def py_wasm_toolchain_suite(*, name, python_version, host, clang, compiler_files, cpython_libs, pyconfig, stdlib, wizer, linkopts = None):
    """Declare a `py_wasm_toolchain` and the `toolchain` that registers it.

    Args:
        name (str): The name of the `toolchain` target; the implementation is `<name>_impl`.
        python_version (str): The `X.Y` of the CPython, which the rules_python toolchain must match.
        host (str): The host the compiler runs on, one of `SUPPORTED_HOSTS`.
        clang (Label): See `py_wasm_toolchain`.
        compiler_files (Label): See `py_wasm_toolchain`.
        cpython_libs (Label): See `py_wasm_toolchain`.
        pyconfig (Label): See `py_wasm_toolchain`.
        stdlib (Label): See `py_wasm_toolchain`.
        wizer (Label): See `py_wasm_toolchain`.
        linkopts (list): See `py_wasm_toolchain`; its default when None.
    """
    if host not in _CONSTRAINTS:
        fail("py_wasm_toolchain_suite {}: unknown host `{}`; one of {}".format(name, host, sorted(_CONSTRAINTS)))

    extra = {} if linkopts == None else {"linkopts": linkopts}
    py_wasm_toolchain(
        name = name + "_impl",
        clang = clang,
        compiler_files = compiler_files,
        cpython_libs = cpython_libs,
        pyconfig = pyconfig,
        python_version = python_version,
        stdlib = stdlib,
        # Not reached by `//...`: analyzing it fetches the archives.
        tags = ["manual"],
        wizer = wizer,
        **extra
    )

    native.toolchain(
        name = name,
        exec_compatible_with = _CONSTRAINTS[host],
        tags = ["manual"],
        target_settings = [Label("@rules_python//python/config_settings:is_python_" + python_version)],
        toolchain = ":" + name + "_impl",
        toolchain_type = Label("//python/wasm:toolchain_type"),
        visibility = ["//visibility:public"],
    )
