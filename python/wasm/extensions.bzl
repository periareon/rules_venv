"""The `py_wasm` module extension: the default toolchains and the archives they are made of.

`py_wasm_module` builds with a `py_wasm_toolchain` (see `py_wasm_toolchain.bzl`).
This extension declares one per supported Python version and per Linux and macOS
host, assembled from a prebuilt CPython for `wasm32-wasi`, the wasi-sdk release
that built it and Wizer, all pinned by version and hash in
`python/wasm/private/versions.bzl`. The archives are `http_archive` repositories
and the toolchains live in a hub repository, `rules_venv_py_wasm_toolchains`,
which `rules_venv` registers, so that nothing is required of a module that
builds a `py_wasm_module`. An archive is fetched only when a module is built,
and only for the host that builds it and the Python version it is for.

A different compiler or CPython is a `py_wasm_toolchain` of one's own; one
archive of a default toolchain is replaced with `override_repo` or
`--override_repository`. The "Toolchains" section of `defs.bzl` describes both.
"""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")
load("@rules_python//python:versions.bzl", "MINOR_MAPPING")
load("//python/wasm/private:toolchain_suite.bzl", "SUPPORTED_HOSTS")
load(
    "//python/wasm/private:versions.bzl",
    "CPYTHON_WASI",
    "CPYTHON_WASI_BUILD_URL",
    "CPYTHON_WASI_STDLIB_URL",
    "WASI_SDK",
    "WIZER",
    "supported_python_versions",
)

_CPYTHON_BUILD = """\
# The build tree of CPython {version} for wasm32-wasi, from cpython-wasi-build.
package(default_visibility = ["//visibility:public"])

exports_files(["pyconfig.h"])

# The interpreter and the static libraries of the modules compiled into it.
filegroup(
    name = "libs",
    srcs = ["libpython{minor}.a"] + glob(["Modules/**/*.a"]),
)
"""

_CPYTHON_STDLIB_BUILD = """\
# The runtime of CPython {version} for wasm32-wasi, from cpython-wasi-build.
package(default_visibility = ["//visibility:public"])

# The standard library as source; `py_wasm_module` compiles it to bytecode
# with the Python toolchain of the same version.
filegroup(
    name = "stdlib",
    srcs = glob(["lib/python{minor}/**/*.py"]),
)
"""

_WASI_SDK_BUILD = """\
package(default_visibility = ["//visibility:public"])

# The compiler finds its resource directory and sysroot relative to itself,
# so an action needs the whole tree, not just `bin/clang`.
filegroup(
    name = "all_files",
    srcs = glob(["**"]),
)

filegroup(
    name = "clang",
    srcs = ["bin/clang"],
)
"""

_WIZER_BUILD = """\
package(default_visibility = ["//visibility:public"])

exports_files(["wizer"])
"""

TOOLCHAINS_REPOSITORY = "rules_venv_py_wasm_toolchains"

# The archives' repositories, named after what they hold so that one can be
# replaced with `override_repo` or `--override_repository`.
def _cpython_repository_name(version):
    return "rules_venv_py_wasm_cpython_{}".format(version.replace(".", "_"))

def _cpython_stdlib_repository_name(version):
    return "{}_stdlib".format(_cpython_repository_name(version))

def _wasi_sdk_repository_name(wasi_sdk, host):
    return "rules_venv_py_wasm_wasi_sdk_{}_{}".format(wasi_sdk, host.replace("-", "_"))

def _wizer_repository_name(host):
    return "rules_venv_py_wasm_wizer_{}".format(host.replace("-", "_"))

_HUB_HEADER = """\
# The default `py_wasm_toolchain`s, written by the `py_wasm` extension of
# rules_venv: one per supported Python version and host.
load("@rules_venv//python/wasm/private:toolchain_suite.bzl", "py_wasm_toolchain_suite")
"""

_HUB_SUITE = """
py_wasm_toolchain_suite(
    name = "{version}-{host}",
    clang = "@{wasi_sdk}//:clang",
    compiler_files = "@{wasi_sdk}//:all_files",
    cpython_libs = "@{cpython}//:libs",
    host = "{host}",
    pyconfig = "@{cpython}//:pyconfig.h",
    python_version = "{version}",
    stdlib = "@{stdlib}//:stdlib",
    wizer = "@{wizer}//:wizer",
)
"""

def _hub_impl(repository_ctx):
    repository_ctx.file("BUILD.bazel", repository_ctx.attr.build_file_content)

_hub = repository_rule(
    doc = "The repository holding the default `py_wasm_toolchain`s.",
    implementation = _hub_impl,
    attrs = {
        "build_file_content": attr.string(mandatory = True),
    },
)

def _py_wasm_impl(module_ctx):
    for minor, cpython in CPYTHON_WASI.items():
        http_archive(
            name = _cpython_repository_name(minor),
            build_file_content = _CPYTHON_BUILD.format(version = cpython.version, minor = minor),
            sha256 = cpython.build_sha256,
            url = CPYTHON_WASI_BUILD_URL.format(version = cpython.version, wasi_sdk = cpython.wasi_sdk),
        )
        http_archive(
            name = _cpython_stdlib_repository_name(minor),
            build_file_content = _CPYTHON_STDLIB_BUILD.format(version = cpython.version, minor = minor),
            sha256 = cpython.stdlib_sha256,
            url = CPYTHON_WASI_STDLIB_URL.format(version = cpython.version, wasi_sdk = cpython.wasi_sdk),
        )
    for release, sdk in WASI_SDK.items():
        for key, host in sdk.hosts.items():
            http_archive(
                name = _wasi_sdk_repository_name(release, key),
                build_file_content = _WASI_SDK_BUILD,
                sha256 = host.sha256,
                strip_prefix = sdk.strip_prefix.format(host = host.name),
                url = sdk.url.format(host = host.name),
            )
    for key, host in WIZER.hosts.items():
        http_archive(
            name = _wizer_repository_name(key),
            build_file_content = _WIZER_BUILD,
            sha256 = host.sha256,
            strip_prefix = WIZER.strip_prefix.format(host = host.name),
            url = WIZER.url.format(host = host.name),
        )

    # The toolchains: a hub that names the archives above, which it sees under
    # the same names because this extension declares them all. Every
    # registered toolchain is analyzed during resolution, and each is gated on
    # rules_python's `is_python_X.Y`, which only exists for the versions that
    # rules_python knows; and a version rules_python maps to a pre-release is
    # left out, since its interpreter could not build the module (see
    # `supported_python_versions`).
    suites = []
    for minor in supported_python_versions(MINOR_MAPPING):
        cpython = CPYTHON_WASI[minor]
        for host in WASI_SDK[cpython.wasi_sdk].hosts:
            if host not in SUPPORTED_HOSTS:
                continue
            suites.append(_HUB_SUITE.format(
                version = minor,
                host = host,
                wasi_sdk = _wasi_sdk_repository_name(cpython.wasi_sdk, host),
                cpython = _cpython_repository_name(minor),
                stdlib = _cpython_stdlib_repository_name(minor),
                wizer = _wizer_repository_name(host),
            ))
    _hub(
        name = TOOLCHAINS_REPOSITORY,
        build_file_content = _HUB_HEADER + "".join(suites),
    )
    return module_ctx.extension_metadata(reproducible = True)

py_wasm = module_extension(
    doc = "Declares the default `py_wasm_toolchain`s and the CPython, wasi-sdk and Wizer archives they are made of.",
    implementation = _py_wasm_impl,
)
