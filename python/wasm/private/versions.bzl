"""The pinned inputs of `py_wasm_module`: CPython for wasm32-wasi, wasi-sdk and Wizer.

Everything a module is built from is named here by version and hash. CPython
comes prebuilt from [cpython-wasi-build](https://github.com/brettcannon/cpython-wasi-build),
Brett Cannon's builds of every CPython release for `wasm32-wasi`; wasi-sdk and
Wizer come from their own releases.
"""

# CPython for wasm32-wasi, one build per minor version `py_wasm_module`
# supports, keyed by the `X.Y` that `python_version` and rules_python's
# `is_python_X.Y` name. Each release publishes two archives: the build tree,
# with `libpython`, `pyconfig.h` and the static libraries of the modules
# compiled into it, and the runtime, with the standard library as source.
# `wasi_sdk` is the release that built it; the toolchain for the version
# compiles with that same release, so that the module's objects match its
# wasi-libc.
#
# A version is offered only when the resolved rules_python maps it to a final
# release (see `supported_python_versions`), so one may be pinned here ahead
# of the rules_python that `rules_venv` tests with. Upstream also builds 3.11
# and 3.12, with wasi-sdk 16 and 20, which only ship x86_64 hosts.
CPYTHON_WASI = {
    "3.13": struct(
        version = "3.13.15",
        wasi_sdk = "24",
        build_sha256 = "3906216e44a7322aa7bc615789df9550a58451a57aa5fbd74bd2a31d9a6f98d1",
        stdlib_sha256 = "67e1c32a85d5e0600c0939f5fd4023ca0127f1a9e81f5499697467bda67af78d",
    ),
    "3.14": struct(
        version = "3.14.7",
        wasi_sdk = "24",
        build_sha256 = "a2a9fca77dc47bb9d2b0dd7d04538f8aa188e5f0a87b362fd569c0d024039100",
        stdlib_sha256 = "2e064d3fb8172471d39d741348efa722349c40b96301f69968dff714999c584b",
    ),
    "3.15": struct(
        version = "3.15.0",
        wasi_sdk = "33",
        build_sha256 = "f8aa92c30247c15dec36f90349148a092ea3daf80cf4eb4859e2a7a69effadb0",
        stdlib_sha256 = "00b791b3729230f97a625087f534d71978433fb1e068e13a9cac8cd3f2541742",
    ),
}

CPYTHON_WASI_BUILD_URL = "https://github.com/brettcannon/cpython-wasi-build/releases/download/v{version}/_build-python-{version}-wasi_sdk-{wasi_sdk}.zip"
CPYTHON_WASI_STDLIB_URL = "https://github.com/brettcannon/cpython-wasi-build/releases/download/v{version}/python-{version}-wasi_sdk-{wasi_sdk}.zip"

# The compiler and sysroot, per release and host. A CPython build names the
# release that built it, whose wasi-libc the module's own objects must match.
WASI_SDK = {
    "24": struct(
        version = "24.0",
        url = "https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-24/wasi-sdk-24.0-{host}.tar.gz",
        strip_prefix = "wasi-sdk-24.0-{host}",
        hosts = {
            "linux-aarch64": struct(name = "arm64-linux", sha256 = "ae6c1417ea161e54bc54c0a168976af57a0c6e53078857886057a71a0d928646"),
            "linux-x86_64": struct(name = "x86_64-linux", sha256 = "c6c38aab56e5de88adf6c1ebc9c3ae8da72f88ec2b656fb024eda8d4167a0bc5"),
            "macos-aarch64": struct(name = "arm64-macos", sha256 = "aeae999396d5f5caa5ce419f52e83c35869d5fd21d40af80acba2c80f51b0b3a"),
            "macos-x86_64": struct(name = "x86_64-macos", sha256 = "4bfc274ae8b68c771dd93e32ad4bd695336ca46b585beb3b1260e5602dbc11a2"),
        },
    ),
    "33": struct(
        version = "33.0",
        url = "https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-33/wasi-sdk-33.0-{host}.tar.gz",
        strip_prefix = "wasi-sdk-33.0-{host}",
        hosts = {
            "linux-aarch64": struct(name = "arm64-linux", sha256 = "4f98ee738c7abb45c81a94d1461fc53cc569d1cd01498951c8184d841a027844"),
            "linux-x86_64": struct(name = "x86_64-linux", sha256 = "0ba8b5bfaeb2adf3f29bab5841d76cf5318ab8e1642ea195f88baba1abd47bce"),
            "macos-aarch64": struct(name = "arm64-macos", sha256 = "85c997a2665ead91673b5bb88b7d0df3fc8900df3bfa244f720d478187bbdc78"),
            "macos-x86_64": struct(name = "x86_64-macos", sha256 = "18f3f201ba9734e6a4455b0b6410690395a55e9ffa9f6f5066f66083a94b93b3"),
        },
    ),
}

# Wizer pre-initializes a module: it runs the interpreter start-up and the
# imports at build time and snapshots the memory into the module.
WIZER = struct(
    version = "11.0.3",
    url = "https://github.com/bytecodealliance/wizer/releases/download/v11.0.3/wizer-v11.0.3-{host}.tar.xz",
    strip_prefix = "wizer-v11.0.3-{host}",
    hosts = {
        "linux-aarch64": struct(name = "aarch64-linux", sha256 = "73bffcbaf736ef24109a48cac431d070c43cb2ee8a14a840576f7aec0133d8d6"),
        "linux-x86_64": struct(name = "x86_64-linux", sha256 = "36016e7f846f38ad09f22eb4bafb99068f038c431eb9613ddf59e31ad8a21414"),
        "macos-aarch64": struct(name = "aarch64-macos", sha256 = "7c54896b456b6ca024af6005ebc5538282dee7cd9f0c9c1155855d29b9c461b1"),
        "macos-x86_64": struct(name = "x86_64-macos", sha256 = "325bcd4758e9509dd81849d7f4ab8cf69cbe084795e138a996c70f471b6f8b83"),
    },
)

def is_final_release(version):
    """Whether a CPython version string names a final release.

    Args:
        version (str): A version, e.g. `3.15.0` or `3.15.0rc3`.

    Returns:
        bool: True for `X.Y.Z`, False for a pre-release or anything else.
    """
    parts = version.split(".")
    if len(parts) != 3:
        return False
    for part in parts:
        if not part.isdigit():
            return False
    return True

def supported_python_versions(minor_mapping):
    """The versions of `CPYTHON_WASI` to offer with a rules_python.

    Args:
        minor_mapping (dict): rules_python's `MINOR_MAPPING`, `X.Y` to the
            full version its `X.Y` toolchain is.

    Returns:
        list: The `X.Y` keys of `CPYTHON_WASI` that rules_python knows (so
        that its `is_python_X.Y` exists) and maps to a final release. A
        pre-release interpreter's bytecode and C ABI may differ from the
        final release embedded in a module; `py_wasm_module` rejects one.
    """
    return [
        version
        for version in CPYTHON_WASI
        if is_final_release(minor_mapping.get(version, ""))
    ]
