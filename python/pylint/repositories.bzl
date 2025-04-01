"""rules_pylint dependencies"""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")
load("@bazel_tools//tools/build_defs/repo:utils.bzl", "maybe")

# buildifier: disable=unnamed-macro
def rules_pylint_dependencies():
    """Defines pylint dependencies"""
    maybe(
        http_archive,
        name = "rules_venv",
        integrity = "sha256-Hb6raL/eMeTEkfbAbM2mBtoua4bcwBr5FwhvGrAMjow=",
        urls = ["https://github.com/periareon/rules_venv/releases/download/0.0.7/rules_venv-0.0.7.tar.gz"],
    )

# buildifier: disable=unnamed-macro
def register_pylint_toolchains(register_toolchains = True):
    """Defines pytest dependencies"""
    if register_toolchains:
        native.register_toolchains(
            str(Label("//python/pylint/toolchain")),
        )
