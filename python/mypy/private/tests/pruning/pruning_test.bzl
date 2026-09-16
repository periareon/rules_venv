"""Unittest to verify that a mypy action reads caches instead of dependency sources."""

load("@bazel_skylib//lib:unittest.bzl", "analysistest", "asserts")
load("@bazel_skylib//rules:write_file.bzl", "write_file")
load("//python:defs.bzl", "py_library")
load("//python/mypy/private:mypy.bzl", "py_mypy_aspect")

_GENERATED_MODULE = '''\
"""A module that only exists as a build output."""


def generated(name: str) -> str:
    """Greet.

    Args:
        name: The name to greet.

    Returns:
        The greeting.
    """
    return f"Hello, {name}"

'''

def _find_action(actions, mnemonic):
    for action in actions:
        if action.mnemonic == mnemonic:
            return action
    fail("Failed to find {} action".format(mnemonic))

def _staged_basenames(action):
    """The basenames the venv is assembled from.

    The manifest the venv is built from is written by an action whose
    inputs are empty -- the files it names travel as arguments -- so what
    reaches the venv has to be read off the command line. Each entry is
    `execpath=rlocationpath`; only the tail is wanted.

    Args:
        action (Action): The `PyVenvRunfiles` action building the manifest.

    Returns:
        dict: The basenames staged in the venv, as a set.
    """
    staged = {}
    for arg in action.argv:
        _, separator, rlocationpath = arg.partition("=")
        if not separator:
            continue
        staged[rlocationpath.rpartition("/")[2]] = None
    return staged

def _pruning_test_impl(ctx):
    env = analysistest.begin(ctx)
    target = analysistest.target_under_test(env)

    mypy_action = _find_action(target.actions, "PyMypy")

    # Basenames rather than paths: a cache is named for the target whose
    # sources it stands in for, and nothing in mypy's own closure shares
    # a name with the files this package builds.
    inputs = {file.basename: None for file in mypy_action.inputs.to_list()}

    for basename in ctx.attr.reads:
        asserts.true(
            env,
            basename in inputs,
            "Expected `{}` among the inputs of {}".format(basename, mypy_action),
        )

    for basename in ctx.attr.prunes:
        asserts.false(
            env,
            basename in inputs,
            "Expected `{}` to be replaced by a cache, but it is an input of {}".format(
                basename,
                mypy_action,
            ),
        )

    # The venv is the only place mypy reads sources from, and a file can
    # be an input of the action without reaching it, so what the action
    # analyzes is asserted there rather than on the inputs.
    if ctx.attr.stages:
        staged = _staged_basenames(_find_action(target.actions, "PyVenvRunfiles"))
        for basename in ctx.attr.stages:
            asserts.true(
                env,
                basename in staged,
                "Expected `{}` in the venv, but it was replaced by a cache".format(
                    basename,
                ),
            )

    return analysistest.end(env)

pruning_test = analysistest.make(
    _pruning_test_impl,
    attrs = {
        "prunes": attr.string_list(
            doc = "Basenames a dependency's cache stands in for, which the action must therefore *not* read.",
        ),
        "reads": attr.string_list(
            doc = "Basenames the action must have among its inputs.",
        ),
        "stages": attr.string_list(
            doc = "Basenames which must reach the venv, no cache being allowed to stand in for them.",
        ),
    },
    extra_target_under_test_aspects = [py_mypy_aspect],
)

def _define_test_targets():
    """Define targets used by the test assertions."""

    py_library(
        name = "pruned_leaf",
        srcs = ["pruned_leaf.py"],
        testonly = True,
    )

    py_library(
        name = "pruned_middle",
        srcs = ["pruned_middle.py"],
        testonly = True,
        deps = [":pruned_leaf"],
    )

    py_library(
        name = "pruned_root",
        srcs = ["pruned_root.py"],
        testonly = True,
        deps = [":pruned_middle"],
    )

    # `find_srcs` only ever checks source files, so a library built
    # entirely out of build outputs is analyzed as one of the unchecked
    # kind, which caches everything it stages.
    write_file(
        name = "pruned_generated_src",
        out = "pruned_generated.py",
        content = _GENERATED_MODULE.splitlines(),
        newline = "unix",
        testonly = True,
    )

    py_library(
        name = "pruned_generated",
        srcs = ["pruned_generated.py"],
        testonly = True,
    )

    py_library(
        name = "pruned_generated_consumer",
        srcs = ["pruned_generated_consumer.py"],
        testonly = True,
        deps = [":pruned_generated"],
    )

    # The same source in two targets. A dependency's cache covering a
    # file says the dependency read it, not that a consumer which also
    # lists it may stop reading it -- pruning it would hand the consumer
    # the empty stand-in in place of the module it is meant to check, and
    # the consumer would report on a file it never read.
    py_library(
        name = "pruned_shared",
        srcs = ["pruned_shared.py"],
        testonly = True,
    )

    py_library(
        name = "pruned_shared_consumer",
        srcs = [
            "pruned_shared.py",
            "pruned_shared_consumer.py",
        ],
        testonly = True,
        deps = [":pruned_shared"],
    )

    # A library with one of each. The source half is checked and so gets
    # cached; the generated half is not, and has to keep travelling.
    write_file(
        name = "pruned_mixed_generated_src",
        out = "pruned_mixed_generated.py",
        content = _GENERATED_MODULE.splitlines(),
        newline = "unix",
        testonly = True,
    )

    py_library(
        name = "pruned_mixed",
        srcs = [
            "pruned_mixed.py",
            "pruned_mixed_generated.py",
        ],
        testonly = True,
    )

    py_library(
        name = "pruned_mixed_consumer",
        srcs = ["pruned_mixed_consumer.py"],
        testonly = True,
        deps = [":pruned_mixed"],
    )

def pruning_test_suite(name):
    """Entry-point macro for the mypy cache pruning test suite.

    The cache exists so that an action stops reading its dependencies'
    sources. Nothing observable breaks when that stops happening -- mypy
    finds the sources, analyzes them again, and reports exactly the same
    result, only slower and shipping the very inputs the cache exists to
    avoid -- so it is asserted on the action directly.

    Only the ordinary shape is covered here, a tree of `py_library`
    targets reached through `deps`, including the two ways a generated
    source can arrive in one. A rule whose Python none of its attributes
    accounts for is deliberately excluded: it caches its whole closure as
    one unit, so reading those sources is what it is for.

    The libraries below are themselves type checked under `--config=mypy`
    like anything else in the workspace, so a cache that resolved a
    module without carrying its types would fail the build rather than
    quietly passing these assertions.

    Args:
        name (str): Name of the macro.
    """

    _define_test_targets()

    cases = {
        "a_dep_cache_does_not_prune_the_targets_own_srcs_test": struct(
            target = ":pruned_shared_consumer",
            reads = [
                "pruned_shared_consumer.py",
                "pruned_shared.py",
                "pruned_shared.mypy.cache",
            ],
            prunes = [],
            stages = ["pruned_shared.py"],
        ),
        "direct_dep_is_cached_test": struct(
            target = ":pruned_middle",
            reads = [
                "pruned_middle.py",
                "pruned_leaf.mypy.cache",
            ],
            prunes = ["pruned_leaf.py"],
        ),
        "generated_dep_is_cached_test": struct(
            target = ":pruned_generated_consumer",
            reads = [
                "pruned_generated_consumer.py",
                "pruned_generated.mypy.cache",
            ],
            prunes = ["pruned_generated.py"],
        ),
        "mixed_dep_keeps_its_generated_srcs_test": struct(
            target = ":pruned_mixed_consumer",
            reads = [
                "pruned_mixed_consumer.py",
                "pruned_mixed.mypy.cache",
                "pruned_mixed_generated.py",
            ],
            prunes = ["pruned_mixed.py"],
        ),
        "transitive_deps_are_cached_test": struct(
            target = ":pruned_root",
            reads = [
                "pruned_root.py",
                "pruned_middle.mypy.cache",
                "pruned_leaf.mypy.cache",
            ],
            prunes = [
                "pruned_middle.py",
                "pruned_leaf.py",
            ],
        ),
    }

    for test_name, case in cases.items():
        pruning_test(
            name = test_name,
            target_under_test = case.target,
            reads = case.reads,
            prunes = case.prunes,
            stages = getattr(case, "stages", []),
        )

    native.test_suite(
        name = name,
        tests = [":" + test_name for test_name in cases],
    )
