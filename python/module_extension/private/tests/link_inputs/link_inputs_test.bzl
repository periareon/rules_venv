"""Tests of what a `py_cc_extension` hands to the linker."""

load("@bazel_skylib//lib:unittest.bzl", "analysistest", "asserts")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _library_names(cc_info):
    """The basenames of every library file in `cc_info`."""
    names = []
    for linker_input in cc_info.linking_context.linker_inputs.to_list():
        for library in linker_input.libraries:
            for field in ["static_library", "pic_static_library", "dynamic_library", "interface_library"]:
                file = getattr(library, field)
                if file:
                    names.append(file.basename)
    return names

def _links_py_cc_libs_test_impl(ctx):
    env = analysistest.begin(ctx)

    link = None
    for action in analysistest.target_actions(env):
        if action.mnemonic == "CppLink":
            link = action
    asserts.true(env, link != None, "Expected a `CppLink` action")
    if link == None:
        return analysistest.end(env)

    # A shared library is linked through its `_solib_<cpu>` symlink, which
    # keeps the basename, so names are what can be compared.
    inputs = [file.basename for file in link.inputs.to_list()]
    expected = _library_names(ctx.attr.libs[CcInfo])
    linked = [name for name in expected if name in inputs]
    asserts.true(
        env,
        len(linked) > 0,
        "Expected one of {} among the link inputs, got {}".format(expected, inputs),
    )

    return analysistest.end(env)

# `cc_shared_library` drops linker inputs whose owner is not in its `deps`
# graph. The interpreter's libraries come through a toolchain, so without
# care that is exactly what happens to them. On Windows `pyconfig.h` asks
# for `python3X.lib` with a `#pragma comment(lib)` and the link then fails.
links_py_cc_libs_test = analysistest.make(
    _links_py_cc_libs_test_impl,
    attrs = {
        "libs": attr.label(
            default = Label("@rules_python//python/cc:current_py_cc_libs"),
            providers = [CcInfo],
        ),
    },
)

def link_inputs_test_suite(name):
    """Define the test suite.

    Args:
        name (str): The name of the suite.
    """
    links_py_cc_libs_test(
        name = "links_py_cc_libs_test",
        target_under_test = ":link_inputs_shared",
    )

    native.test_suite(
        name = name,
        tests = [":links_py_cc_libs_test"],
    )
