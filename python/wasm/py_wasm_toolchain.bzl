"""The toolchain `py_wasm_module` builds with."""

load("@bazel_skylib//lib:paths.bzl", "paths")

TOOLCHAIN_TYPE = str(Label("//python/wasm:toolchain_type"))

# What CPython's own wasm32-wasi build links against beyond libc: wasi-libc's
# emulations of signals, getpid and process clocks, and the dl and m stubs.
DEFAULT_LINKOPTS = [
    "-ldl",
    "-lwasi-emulated-signal",
    "-lwasi-emulated-getpid",
    "-lwasi-emulated-process-clocks",
    "-lm",
]

def _py_wasm_toolchain_impl(ctx):
    clang = ctx.file.clang
    if not clang.basename.startswith("clang"):
        fail(
            "`clang` of {} is `{}`, but `py_wasm_module` compiles and links with the clang of a ".format(ctx.label, clang.basename) +
            "wasi-sdk, the release that built `cpython_libs` so that their wasi-libc match. No other " +
            "compiler has the `wasm32-wasi` target and linker flags the rule uses.",
        )
    sysroot = paths.normalize(paths.join(clang.dirname, "..", ctx.attr.sysroot))

    version = ctx.attr.python_version
    parts = version.split(".")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        fail("`python_version` of {} is `{}`; it must be `X.Y`, e.g. `3.14`".format(ctx.label, version))

    # The standard library's root: the directory holding `os.py`.
    stdlib_dir = None
    for file in ctx.files.stdlib:
        if file.basename == "os.py" and (stdlib_dir == None or len(file.dirname) < len(stdlib_dir)):
            stdlib_dir = file.dirname
    if stdlib_dir == None:
        fail("`stdlib` of {} has no `os.py`".format(ctx.label))

    # `libpython` first: the module libraries resolve what it leaves undefined.
    libs = [lib for lib in ctx.files.cpython_libs if lib.basename.startswith("libpython")]
    if not libs:
        fail("`cpython_libs` of {} has no `libpython`".format(ctx.label))
    libs.extend([lib for lib in ctx.files.cpython_libs if not lib.basename.startswith("libpython")])

    return [platform_common.ToolchainInfo(
        clang = clang,
        compiler_files = depset([clang], transitive = [ctx.attr.compiler_files[DefaultInfo].files]),
        sysroot = sysroot,
        cpython_libs = libs,
        linkopts = ctx.attr.linkopts,
        pyconfig = ctx.file.pyconfig,
        stdlib_files = depset(ctx.files.stdlib),
        stdlib_dir = stdlib_dir,
        python_version = version,
        wizer = ctx.file.wizer,
    )]

py_wasm_toolchain = rule(
    doc = """\
Declare what `py_wasm_module` builds with: a C compiler for `wasm32-wasi`, a
CPython built for it, and optionally Wizer.

`rules_venv` registers toolchains of this kind for Python 3.13 and 3.14 on
Linux, macOS and Windows hosts from archives it fetches (see `extensions.bzl`); a module
that wants a compiler or a CPython of its own declares one and registers it with
`register_toolchains` or `--extra_toolchains`.

A toolchain is for one Python version: the headers that compile the module's
host code and the interpreter that produces its bytecode are the rules_python
toolchain's, so the two must be the same `X.Y`. Registering a toolchain with
rules_python's `is_python_X.Y` as a `target_setting`, as below, makes it
eligible only then, and a module's `python_version` selects it.

Requirements: `clang` must be the clang of a wasi-sdk (this rule fails on any
other driver), of the release that built `cpython_libs`, so that their wasi-libc
match; `cpython_libs` holds `libpython3.X.a` and the static libraries of the
modules compiled into it; `pyconfig` is that build's `pyconfig.h`, which stands
in for the host one of the rules_python toolchain's headers; `linkopts` names
what that build links against beyond libc, by default what CPython's own
`wasm32-wasi` configuration uses.

```python
load("@rules_venv//python/wasm:defs.bzl", "py_wasm_toolchain")

py_wasm_toolchain(
    name = "py_wasm_toolchain",
    clang = "@my_wasi_sdk//:bin/clang",
    compiler_files = "@my_wasi_sdk//:all_files",
    cpython_libs = "@my_cpython_wasi//:libs",
    pyconfig = "@my_cpython_wasi//:pyconfig.h",
    python_version = "3.14",
    stdlib = "@my_cpython_wasi_stdlib//:stdlib",
    wizer = "@my_wizer//:wizer",
)

toolchain(
    name = "toolchain",
    exec_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
    target_settings = ["@rules_python//python/config_settings:is_python_3.14"],
    toolchain = ":py_wasm_toolchain",
    toolchain_type = "@rules_venv//python/wasm:toolchain_type",
)
```
""",
    implementation = _py_wasm_toolchain_impl,
    attrs = {
        "clang": attr.label(
            doc = "The `clang` driver of a wasi-sdk, which also links.",
            allow_single_file = True,
            cfg = "exec",
            mandatory = True,
        ),
        "compiler_files": attr.label(
            doc = "Every file of the wasi-sdk: the driver finds its resource directory and sysroot relative to itself.",
            cfg = "exec",
            mandatory = True,
        ),
        "cpython_libs": attr.label(
            doc = "`libpython3.X.a` and the static libraries of the modules compiled into it, from a CPython build for `wasm32-wasi`.",
            allow_files = [".a"],
            mandatory = True,
        ),
        "linkopts": attr.string_list(
            doc = "Linker flags for what `cpython_libs` needs beyond libc, after the libraries on the command line. The default is what CPython's `wasm32-wasi` configuration links: wasi-libc's emulated signals, getpid and process clocks, and `dl` and `m`.",
            default = DEFAULT_LINKOPTS,
        ),
        "pyconfig": attr.label(
            doc = "The `pyconfig.h` of that build, which describes `wasm32-wasi` to the headers.",
            allow_single_file = [".h"],
            mandatory = True,
        ),
        "python_version": attr.string(
            doc = "The `X.Y` of the CPython, e.g. `3.14`. The rules_python toolchain a module builds with must be the same.",
            mandatory = True,
        ),
        "stdlib": attr.label(
            doc = "The standard library of that CPython as source, with `os.py` at its root.",
            allow_files = [".py"],
            mandatory = True,
        ),
        "sysroot": attr.string(
            doc = "The sysroot, relative to the directory holding the driver's `bin/`.",
            default = "share/wasi-sysroot",
        ),
        "wizer": attr.label(
            doc = "Wizer, to pre-initialize modules. Without it `preinitialize` cannot be used.",
            allow_single_file = True,
            cfg = "exec",
            executable = True,
        ),
    },
)
