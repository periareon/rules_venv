"""The `py_wasm` module extension: the default toolchains and the archives they are made of.

`py_wasm_module` builds with a `py_wasm_toolchain` (see `py_wasm_toolchain.bzl`).
This extension declares one per supported Python version and per Linux, macOS
and Windows host, assembled from a prebuilt CPython for `wasm32-wasi`, the
wasi-sdk release that built it and Wizer, all pinned by version and hash in
`python/wasm/private/versions.bzl`. The archives are `http_archive` repositories
and the toolchains live in a hub repository, `rules_venv_py_wasm_toolchains`,
which `rules_venv` registers, so that nothing is required of a module that
builds a `py_wasm_module`. An archive is fetched only when a module is built,
and only for the host that builds it and the Python version it is for.

The CPython of a version comes in variants that differ in how the interpreter
is compiled (`CPYTHON_WASI` in `versions.bzl` says which and why). Every
variant's archives are declared, under names that say which they hold, and the
one toolchain of a version selects among them on the
`//python/wasm:cpython_variant` flag, whose default is the version's own
default; `--@rules_venv//python/wasm:cpython_variant=stock` picks CPython's own
build. Nothing is fetched until a module is built, and then only the variant
the flag selects.

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
    "WASI_SDK",
    "WIZER",
    "cpython_wasi_urls",
    "supported_python_versions",
)

_CPYTHON_BUILD = """\
# The build tree of CPython {version} for wasm32-wasi ({variant}), from cpython-wasi-build.
package(default_visibility = ["//visibility:public"])

exports_files(["pyconfig.h"])

# The interpreter and the static libraries of the modules compiled into it.
filegroup(
    name = "libs",
    srcs = ["libpython{minor}.a"] + glob(["Modules/**/*.a"]),
)
"""

_CPYTHON_STDLIB_BUILD = """\
# The runtime of CPython {version} for wasm32-wasi ({variant}), from cpython-wasi-build.
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
    srcs = ["bin/clang{exe}"],
)
"""

_WIZER_BUILD = """\
package(default_visibility = ["//visibility:public"])

exports_files(["wizer{exe}"])
"""

TOOLCHAINS_REPOSITORY = "rules_venv_py_wasm_toolchains"

# The archives' repositories, named after what they hold so that one can be
# replaced with `override_repo` or `--override_repository`.
def _cpython_repository_name(version, variant):
    return "rules_venv_py_wasm_cpython_{}_{}".format(version.replace(".", "_"), variant.replace("-", "_"))

def _cpython_stdlib_repository_name(version, variant):
    return "{}_stdlib".format(_cpython_repository_name(version, variant))

_VARIANT_SETTING = "@rules_venv//python/wasm:cpython_variant_{}"

def _cpython_select(cpython, minor, target):
    """A `select()` over the variant flag for one target of a version's CPython archives.

    The flag's `default` value means the version's default variant. There is no
    `//conditions:default` branch on purpose: a variant the version does not have
    then matches nothing and `no_match_error` says which it has, where a
    catch-all would fall back silently.
    """
    branches = {}
    for variant in sorted(cpython.variants):
        repository = _cpython_stdlib_repository_name(minor, variant) if target == "stdlib" else _cpython_repository_name(minor, variant)
        branches[_VARIANT_SETTING.format(variant.replace("-", "_"))] = "@{}//:{}".format(repository, target)
    branches[_VARIANT_SETTING.format("default")] = branches[_VARIANT_SETTING.format(cpython.default.replace("-", "_"))]
    return "select({}, no_match_error = {})".format(
        json.encode_indent(branches, prefix = "        ", indent = "    "),
        json.encode("CPython {} for wasm32-wasi has no such variant; its variants are {}".format(minor, ", ".join(sorted(cpython.variants)))),
    )

def _wasi_sdk_repository_name(wasi_sdk, host):
    return "rules_venv_py_wasm_wasi_sdk_{}_{}".format(wasi_sdk, host.replace("-", "_"))

def _wizer_repository_name(host):
    return "rules_venv_py_wasm_wizer_{}".format(host.replace("-", "_"))

def _exe(host):
    """The suffix of an executable on `host`, a key of `SUPPORTED_HOSTS`."""
    return ".exe" if host.startswith("windows-") else ""

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
    cpython_libs = {libs},
    host = "{host}",
    pyconfig = {pyconfig},
    python_version = "{version}",
    stdlib = {stdlib},
    wizer = "@{wizer}//:wizer{exe}",
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
        for variant, archive in cpython.variants.items():
            build_url, stdlib_url = cpython_wasi_urls(cpython, variant)
            http_archive(
                name = _cpython_repository_name(minor, variant),
                build_file_content = _CPYTHON_BUILD.format(version = cpython.version, minor = minor, variant = variant),
                sha256 = archive.build_sha256,
                url = build_url,
            )
            http_archive(
                name = _cpython_stdlib_repository_name(minor, variant),
                build_file_content = _CPYTHON_STDLIB_BUILD.format(version = cpython.version, minor = minor, variant = variant),
                sha256 = archive.stdlib_sha256,
                url = stdlib_url,
            )
    for release, sdk in WASI_SDK.items():
        for key, host in sdk.hosts.items():
            http_archive(
                name = _wasi_sdk_repository_name(release, key),
                build_file_content = _WASI_SDK_BUILD.format(exe = _exe(key)),
                sha256 = host.sha256,
                strip_prefix = sdk.strip_prefix.format(host = host.name),
                url = sdk.url.format(host = host.name),
            )
    for key, host in WIZER.hosts.items():
        http_archive(
            name = _wizer_repository_name(key),
            build_file_content = _WIZER_BUILD.format(exe = _exe(key)),
            sha256 = host.sha256,
            strip_prefix = WIZER.strip_prefix.format(host = host.name),
            url = WIZER.url.format(host = host.name, archive = host.archive),
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
                exe = _exe(host),
                wasi_sdk = _wasi_sdk_repository_name(cpython.wasi_sdk, host),
                libs = _cpython_select(cpython, minor, "libs"),
                pyconfig = _cpython_select(cpython, minor, "pyconfig.h"),
                stdlib = _cpython_select(cpython, minor, "stdlib"),
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
