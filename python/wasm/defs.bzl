"""# py_wasm_module

Build Python into a self-contained WebAssembly module: CPython and the sources
of `py_library` targets, callable from any WebAssembly runtime, with no Python
interpreter on the host.

The module is CPython built for `wasm32-wasi` and linked with an in-module
implementation of the WASI functions it would otherwise import, so that it
imports nothing and a runtime that provides no host functions at all can
instantiate it. Inside it run the unmodified sources of the `py_library` targets
named by `deps`, served by an importer over a bundle linked into the module,
together with the standard library as bytecode. By default the interpreter is
started and the entry module imported at build time, with Wizer, and the memory
snapshot becomes the module, so a call does not pay for start-up.

## Setup

Nothing beyond depending on `rules_venv` and registering, with rules_python, a
hermetic Python toolchain of a version the rule supports: 3.13, 3.14, and 3.15
once rules_python maps it to a final release. Modules are built with a
`py_wasm_toolchain`, and `rules_venv` registers one for each such version and
each Linux and macOS host (x86_64 and arm64), made of the
`wasm32-wasi` build of that CPython release from
[cpython-wasi-build](https://github.com/brettcannon/cpython-wasi-build), the
wasi-sdk release that built it and Wizer, which its `py_wasm` extension fetches
when a module is first built. A compiler or CPython of one's own is another
`py_wasm_toolchain`; see "Toolchains" below.

## Requirements

- A hermetic rules_python toolchain of the module's `python_version`, a final
  release. Its C headers compile the module's host code and its interpreter
  produces the bytecode for the one in the module, so the two must be the same
  `X.Y` and a pre-release, whose bytecode and ABI may differ, is refused; the
  rule fails on either, and the build tools check again when they run.
- A `py_wasm_toolchain` for that version on the host, and Wizer when
  `preinitialize` is on. The rule fails when `preinitialize` has no Wizer.
- Code that runs on CPython for WASI: a source the embedded interpreter cannot
  import fails at build time with its traceback when `preinitialize` is on,
  else at the first call.

## Use

```python
load("@rules_venv//python:defs.bzl", "py_library")
load("@rules_venv//python/wasm:defs.bzl", "py_wasm_module")

py_library(
    name = "entry",
    srcs = ["entry.py"],
    deps = ["//my_rules:lib"],
)

py_wasm_module(
    name = "my_rules",
    entry = "my_rules.wasm.entry",
    exports = ["run"],
    python_version = "3.14",
    deps = [":entry"],
)
```

The entry module defines one function per export, taking the input of the call
as `bytes` and returning `bytes`, or `(bytes, code)` to set the call's return
code:

```python
import json

def run(payload: bytes) -> bytes:
    request = json.loads(payload)
    ...
    return json.dumps(response).encode("utf-8")
```

## Calling the module

The module exports its memory as `memory`, an allocator, and one function per
entry of `exports`:

```text
allocate(size: u32, align: u32) -> u32            the address of `size` bytes
<export>(input: u32, input_len: u32,
         out_ptr: u32, out_len: u32) -> u32       the return code
```

A host writes the input into memory it obtained from `allocate`, calls the
export with the addresses of two more words to receive the output's address and
length, and reads the output back from memory. The return code is 0, or the
code the function returned with `(bytes, code)`, or 2 when it raised, in which
case the output holds the traceback and what was written to standard error.
With Python's `wasmtime` package:

```python
import wasmtime

store = wasmtime.Store(wasmtime.Engine())
module = wasmtime.Module.from_file(store.engine, "my_rules.wasm")
exports = wasmtime.Instance(store, module, []).exports(store)
memory = exports["memory"]

payload = json.dumps(request).encode("utf-8")
input_ptr = exports["allocate"](store, len(payload), 1)
memory.write(store, payload, input_ptr)
out = exports["allocate"](store, 8, 4)
code = exports["run"](store, input_ptr, len(payload), out, out + 4)
out_ptr = int.from_bytes(memory.read(store, out, out + 4), "little")
out_len = int.from_bytes(memory.read(store, out + 4, out + 8), "little")
output = bytes(memory.read(store, out_ptr, out_ptr + out_len))
```

A call changes the instance's memory, and instances are independent, so a host
that wants every call to be a function of its input alone instantiates the
module per call. Any runtime that can instantiate a module without imports and
call exports with integer arguments can be the host; `examples/py_wasm_module`
in the rules_venv repository has a Bazel repository rule calling a module with
`repository_ctx.execute_wasm` this way.

## What a call can do

Nothing outside the module: no files, network, clock or processes. Standard
output and error are captured inside the module; the error stream of a failed
call is returned with the traceback. A program that needs the outside world
receives what it needs in its input and describes what it wants done in its
output, in rounds if need be. Bytes cross the boundary unchanged in both
directions.

## The CPython

The CPython in a module is an unmodified release built for `wasm32-wasi` by
cpython-wasi-build, pinned by version and hash in
`python/wasm/private/versions.bzl` together with the wasi-sdk release that
built it. Of that build the rule uses `pyconfig.h`, `libpython` and the
libraries of the modules compiled into it, and its standard library as source;
the public headers are the rules_python toolchain's, and the bytecode is
produced at build time by that toolchain's interpreter, which is why the two
must be the same version.

## Toolchains

A module is built with a `py_wasm_toolchain`: the clang of a wasi-sdk, a
CPython built for `wasm32-wasi` (`libpython`, the libraries of its modules,
its `pyconfig.h` and its standard library), the flags that CPython links with,
and Wizer. Two of rules_python's toolchains take part as well, resolved for the
same Python version: its C toolchain, for the headers, and its exec tools
toolchain, for the interpreter that produces the module's bytecode.

### The defaults

`rules_venv` registers a toolchain for every Python version pinned in
`python/wasm/private/versions.bzl` that the resolved rules_python maps to a
final release, 3.13 and 3.14 today, for Linux and macOS on x86_64 and arm64.
Its `py_wasm` extension declares the archives and writes the toolchains into
the repository `@rules_venv_py_wasm_toolchains`. Nothing is fetched until a
module is built, and then only what the resolved toolchain needs. Each
toolchain is gated on rules_python's `is_python_X.Y`, which a module's
`python_version` sets, so the embedded CPython always matches the Python
toolchain the module is built with; a version rules_python maps to a
pre-release is left out, and the rule refuses one, since its bytecode and ABI
may differ from the release's.

### One of your own

Declare a `py_wasm_toolchain` and a `toolchain` gated on `is_python_X.Y`, as in
the documentation of `py_wasm_toolchain`, and register it with
`register_toolchains` in `MODULE.bazel` or with `--extra_toolchains`. A root
module's toolchains take precedence over `rules_venv`'s, which remain as the
fallback for other versions and hosts. Reasons to: a CPython built differently,
with other configure options or patches; a version or host `rules_venv` has no
build for; a policy of building from source; or a newer wasi-sdk, which must be
the release that built the CPython so that their wasi-libc agree. `linkopts`
and `stdlib` of the toolchain cover smaller adjustments: what the CPython links
against, and which standard library modules go into a module.

### Replacing one archive

To keep a default toolchain but swap one of its parts, point the extension's
repository for it elsewhere. In `MODULE.bazel`:

```python
py_wasm = use_extension("@rules_venv//python/wasm:extensions.bzl", "py_wasm")
override_repo(py_wasm, rules_venv_py_wasm_cpython_3_14 = "my_cpython_wasi")
```

or, for a checkout on disk, `--override_repository=rules_venv++py_wasm+rules_venv_py_wasm_cpython_3_14=<directory>`.
The repositories are `rules_venv_py_wasm_cpython_<X_Y>` (the build tree:
`libpython3.X.a`, `pyconfig.h`, `Modules/**/*.a`), `..._cpython_<X_Y>_stdlib`
(`lib/python3.X/**/*.py`), `rules_venv_py_wasm_wasi_sdk_<release>_<host>` and
`rules_venv_py_wasm_wizer_<host>`; a replacement provides the same targets as
the BUILD files in `extensions.bzl`.
"""

load("//python/wasm/private:py_wasm_module.bzl", _py_wasm_module = "py_wasm_module")
load(":py_wasm_toolchain.bzl", _py_wasm_toolchain = "py_wasm_toolchain")

py_wasm_module = _py_wasm_module
py_wasm_toolchain = _py_wasm_toolchain
