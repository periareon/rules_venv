"""Entry point for running Mypy from Bazel."""

import argparse
import io
import os
import shutil
import sys
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import NamedTuple

import mypy
from mypy.main import main as mypy_main
from python.runfiles import Runfiles

from python.mypy.private import (
    mypy_cache,
    mypy_metadata,
    mypy_modules,
    mypy_options,
    mypy_paths,
)

# The module a cached run imports to pull in what it is meant to analyze.
# Its own entries are never published: the name is the same in every
# action but the contents are not, so two of them in one cache would be
# a collision.
_PROBE_MODULE = "rules_venv_mypy_probe"

# Where a re-export is written for each name a covered source answers to
# besides the one it was published under. Sits inside the working
# directory, so that it goes when that does. See
# `mypy_modules.stage_alternates`.
_SHIM_DIR = ".mypy-shim"

# Set this in the action environment (`--action_env`) to print the output
# an action would otherwise hold back and to run mypy with `-v`. The
# actions that publish a cache without reporting on it discard everything
# mypy says, which leaves no way to see why a module came out stale.
_DEBUG_ENV_VAR = "RULES_VENV_MYPY_DEBUG"


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
    """
    runfile = runfiles.Rlocation(rlocationpath, source_repo=os.getenv("TEST_WORKSPACE"))
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def _maybe_runfile(arg: str) -> Path:
    """Parse an argument into a path while resolving runfiles.

    Not all contexts this script runs in will use runfiles. In
    these cases the functon is a noop.

    Raises:
        OSError: If a test has no runfiles to resolve through.
    """
    if "BAZEL_TEST" not in os.environ:
        return Path(arg)

    runfiles = Runfiles.Create()
    if not runfiles:
        raise OSError("Failed to locate runfiles")
    return _rlocation(runfiles, arg)


def _venv_source(rlocationpath: str) -> Path:
    """Find a source in the venv, which is where mypy resolves modules.

    Sources are read out of the venv rather than the execution root
    because that is the copy consumers will resolve. mypy derives a
    module's name from the search path it was found under, and only the
    venv's copy lies beneath an import root; naming the execution root's
    copy files the module under a bare name -- `first_party_1` rather
    than `pkg.first_party_1` -- which is not a name any consumer looks
    up. The cache would then be a set of entries nothing matches, and a
    consumer that had pruned the sources would find only the empty
    stand-in.

    The tree is read directly rather than through the runfiles library,
    which under a manifest answers with wherever the file really is -- in
    the source checkout, for anything checked in. mypy takes the
    directory of a source that no package encloses as a search path, so
    answering that way would put the checkout on the search path and let
    mypy resolve modules from directories next to the file that no target
    ever declared.

    Args:
        rlocationpath: The source's key within the venv's tree.

    Returns:
        The file, as named relative to the execution root where the
        environment names no tree.
    """
    runfiles_dir = _runfiles_dir()
    return Path(runfiles_dir, rlocationpath) if runfiles_dir else Path(rlocationpath)


def _workspace_root(workspace_name: str) -> str:
    """The root the workspace's sources sit under, which names their modules.

    mypy names a module after the import root its file was found under,
    so without this root the workspace's files come out under bare names
    -- `consumer` rather than `pkg.consumer` -- which is neither what the
    code imports nor what a diagnostic should say.

    The wrapper chooses the venv's tree at runtime, so nothing in
    Starlark can pass it down; it arrives in the environment instead.

    Only an uncached run asks for this. A cached one works in the tree
    itself and derives the root from there, `_cached_paths` having the
    working directory already.

    Returns:
        The root, empty where the environment names no tree.
    """
    runfiles_dir = _runfiles_dir()
    if not runfiles_dir:
        return ""
    return os.path.join(runfiles_dir, workspace_name)


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    # A target with a large dependency closure gets one `--dep-cache` per
    # transitive dependency, which is more than a command line holds, so
    # Bazel is allowed to pass them in a params file instead.
    parser = argparse.ArgumentParser(fromfile_prefix_chars="@")

    parser.add_argument(
        "--config-file",
        required=True,
        type=_maybe_runfile,
        help="The configuration file (mypy.ini).",
    )
    parser.add_argument(
        "--file",
        dest="sources",
        action="append",
        default=[],
        type=_venv_source,
        help="The source file to run mypy on, as an rlocationpath.",
    )
    parser.add_argument(
        "--workspace_name",
        type=str,
        required=True,
        help="The name of the repository the workspace's own sources are in.",
    )
    parser.add_argument(
        "--marker",
        type=Path,
        help="The file to create as an indication that the action succeeded.",
    )
    parser.add_argument(
        "--cache-out",
        type=Path,
        help=(
            "Where to write this target's incremental cache. Passing this "
            "enables cache mode, in which dependencies may be provided as "
            "caches instead of sources."
        ),
    )
    parser.add_argument(
        "--manifest",
        dest="manifest",
        action="append",
        default=[],
        type=str,
        help=(
            "A path to record in `--cache-out`'s manifest, as an "
            "rlocationpath. Consumers stand an empty file in at each of "
            "these so module resolution finds something to attach the "
            "cached types to. Covers the analyzed sources and the files "
            "resolution needs to see but mypy never reads, such as PEP 561 "
            "`py.typed` markers."
        ),
    )
    parser.add_argument(
        "--dep-cache",
        dest="dep_caches",
        action="append",
        default=[],
        type=Path,
        help="A dependency's cache, as written by its own `--cache-out`.",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help=(
            "Publish type information without judging it. Nothing mypy "
            "says fails this action: an error is not reported, and a "
            "refusal to analyze at all publishes an empty cache and leaves "
            "consumers reading the sources as they did before. For "
            "dependencies that are not themselves checked, such as "
            "third-party packages."
        ),
    )
    parser.add_argument(
        "--stdlib",
        action="store_true",
        help=(
            "Analyze the standard library instead of `--file` sources, "
            "producing the cache that every other mypy action inherits."
        ),
    )

    parsed_args = parser.parse_args(args)

    parsed_args.workspace_root = _workspace_root(parsed_args.workspace_name)

    if not parsed_args.cache_out:
        for flag, value in (
            ("--dep-cache", parsed_args.dep_caches),
            ("--manifest", parsed_args.manifest),
            ("--cache-only", parsed_args.cache_only),
            ("--stdlib", parsed_args.stdlib),
        ):
            if value:
                parser.error(f"{flag} requires --cache-out.")

    if parsed_args.cache_only and parsed_args.marker:
        parser.error("--cache-only produces no result to mark; drop --marker.")

    if parsed_args.stdlib:
        if parsed_args.sources:
            parser.error("--stdlib supplies its own sources; drop --file.")
        if not parsed_args.cache_only:
            parser.error("--stdlib is not a check; pass --cache-only.")
    elif not parsed_args.sources:
        parser.error("No source files were provided.")

    return parsed_args


def _runfiles_dir() -> str:
    """The venv's runfiles tree, which is where mypy resolves modules.

    Dependencies reach mypy through the venv rather than the execution
    root, so this is the root the manifest's rlocationpaths are relative
    to and the only place a stand-in for a pruned source does any good.
    """
    return os.environ.get("RULES_VENV_RUNFILES_DIR", os.environ.get("RUNFILES_DIR", ""))


def _cached_paths(cwd: Path, workspace_name: str) -> list[str]:
    """The roots a cached run searches, deepest first.

    These are the venv's own `sys.path` entries within the tree: the root
    of each repository whose sources the venv carries, and each root some
    target's `imports` declares, which is what gives a file the shorter
    name its own package spells.

    Naming them to mypy rather than leaving them to be found on
    `sys.path` is what makes them analyzable at all. mypy treats
    everything it reaches through the interpreter's own path as an
    installed distribution, and PEP 561 says an installed package with no
    `py.typed` marker is not to be analyzed. A `py_library` is source
    this build owns rather than a wheel someone published, and no such
    target has reason to carry the marker, so every one of them would be
    skipped and every consumer would get `Any`.

    Installed packages are left to be found the other way, which is why
    anything below a `site-packages` is passed over here: a wheel unpacks
    into one of those rather than into the repository itself, so PEP 561
    goes on deciding what it is there to decide.

    Deepest first because that is how mypy names a file -- for the
    longest root it sits under -- and the deeper root is the one whose
    name the code actually spells.

    Args:
        cwd: mypy's working directory, which is the runfiles tree the
            repositories sit in.
        workspace_name: The workspace's own repository, whose root is
            named whether or not anything declared it.

    Returns:
        The search paths.
    """
    tree = str(cwd)
    roots = [
        entry
        for entry in dict.fromkeys(sys.path)
        if mypy_modules.under(entry, tree)
        and mypy_modules.SITE_PACKAGES not in Path(entry).parts
    ]

    workspace_root = os.path.join(tree, workspace_name)
    if workspace_root not in roots:
        roots.append(workspace_root)

    # A stable sort, so roots of equal depth keep the order the venv put
    # them in and every action reaches the same list.
    roots.sort(key=lambda root: root.count(os.sep), reverse=True)
    return roots


def _uncached_paths(workspace_root: str) -> list[str]:
    """The roots an uncached run searches.

    Nothing this run names outlives the process, so the roots can be
    taken as the interpreter gives them and a file can be named for the
    deepest one it sits under. That is both cheaper than the cached run's
    arrangement and closer to what the venv itself does: no re-export to
    write per file, and no need to be told the closure in order to write
    them.

    Subdirectory entries that contain an `__init__.py` are skipped. When
    `explicit_package_bases = True` mypy treats every `mypy_path` entry
    as a package root and scans directories with `__init__.py` for
    sibling modules, so such a directory reachable from the workspace
    root as well leaves mypy finding the same file under two names, which
    it stops on. Directories without one (generated stubs, say) are only
    reachable through the explicit `imports` path and are safe.
    """
    if not workspace_root:
        return []

    paths = [
        entry
        for entry in dict.fromkeys(sys.path)
        if mypy_modules.under(entry, workspace_root)
        and not (
            entry != workspace_root
            and os.path.isfile(os.path.join(entry, "__init__.py"))
        )
    ]

    # Last: the narrower roots an `imports` adds are meant to be searched
    # ahead of the one they sit inside.
    if workspace_root not in paths:
        paths.append(workspace_root)
    return paths


def _is_probe_entry(key: str) -> bool:
    """Whether a cache entry belongs to the probe rather than to a module."""
    return mypy_modules.entry_module(key) == _PROBE_MODULE


def _typeshed_dir() -> Path | None:
    """The typeshed mypy has bundled, if it is where it is expected."""
    if not mypy.__file__:
        return None

    typeshed = Path(mypy.__file__).parent / "typeshed"
    return typeshed if typeshed.is_dir() else None


def _typeshed_flags(cwd: Path) -> list[str]:
    """Point mypy at its own typeshed by a name relative to where it runs.

    Left alone, mypy finds typeshed through `mypy.__file__`, which CPython
    absolutized at import time -- before `mypy_paths` could have
    any say -- and that path runs through the venv's own temporary
    directory, whose name is new on every run. It ends up in the metadata
    of every stub mypy reads, so the interface hash of every stub, and
    with it the recorded dependency hashes of every module that imports
    one, would differ from action to action. Nothing would ever be found
    fresh.

    The venv is self-contained, so typeshed sits at a fixed place within
    it and a relative name is the same string everywhere.

    `custom_typeshed_dir` is not among mypy's cache-affecting options, so
    naming the directory here does not stop a cache written by one action
    from being read by another.

    Returns:
        The typeshed flags, or nothing when mypy has no bundled typeshed
        to name.
    """
    typeshed = _typeshed_dir()
    if not typeshed:
        return []

    return ["--custom-typeshed-dir", os.path.relpath(typeshed, cwd)]


def _stdlib_module_names() -> list[str]:
    """Every standard library module mypy can resolve, submodules included.

    Read from the bundled typeshed's directory listing when it can be
    found, because `sys.stdlib_module_names` holds only top-level names.
    That omission is expensive: `urllib.parse` and
    `xml.etree.ElementTree` would then be absent from the shared cache
    and duplicated into every target that touches them. The listing is
    also exact, so nothing unresolvable goes into the probe.

    Falls back to `sys.stdlib_module_names` if the bundled stubs are not
    where they are expected. Names typeshed does not cover then simply
    fail to resolve, which is a non-blocking error and so does not fail a
    cache-only run.
    """
    names: set[str] = set()

    bundled = _typeshed_dir()
    typeshed = bundled / "stdlib" if bundled else None
    if typeshed and typeshed.is_dir():
        for stub in typeshed.rglob("*.pyi"):
            name = mypy_modules.dotted_name(stub.relative_to(typeshed).parts)
            if name:
                names.add(name)

    if not names:
        names = set(sys.stdlib_module_names)

    return sorted(name for name in names if not name.startswith("_"))


def _write_probe(cwd: Path, modules: Iterable[str]) -> str:
    """Write a source that imports the given modules and nothing else.

    Analyzing a module by importing it, rather than by naming its file to
    mypy, is what makes a cache usable by the targets downstream. mypy
    treats a file it was handed as something the user asked about: it is
    resolved without an import search, and its diagnostics are the
    caller's business. A consumer reaches that same module the only way
    it can, by import, and mypy then applies PEP 561 to decide whether
    the package may be looked at and silences whatever it finds inside an
    installed one. Analyzing by import in the producer too keeps the two
    in step -- the cache holds exactly the modules a consumer can resolve,
    recorded with the same dependencies and the same silence.

    Returns:
        The probe's path, relative to the working directory.
    """
    probe = f"{_PROBE_MODULE}.py"
    (cwd / probe).write_text(
        "".join(f"import {name}\n" for name in sorted(set(modules))), encoding="utf-8"
    )
    return probe


def _working_dir() -> Path:
    """Where a cached mypy run works, which is the venv's own tree.

    Where mypy runs decides what goes into the cache. mypy serializes
    each module's path into the module's own data and takes the interface
    hash over those bytes, so two actions analyzing the same file have to
    record the same path for it or neither can use the other's work.
    Under `--bazel` those paths are relative to the working directory.

    The venv's runfiles tree is the directory that makes them agree.
    Every file mypy reads is rendered into it -- see `_cache_venv` in
    `mypy.bzl` -- so a path relative to it is that file's rlocationpath,
    the same string in every action. Anywhere else reaches at least some
    files through the execution root, and the cache comes out worthless
    to every other machine while still looking perfectly valid. Running
    where the files already are also keeps the run to one set of names,
    so mypy's paths, the manifest's entries and the search roots need no
    translating between them.

    Nothing collides in here. The tree is private to the process -- the
    venv wrapper builds it under a fresh temporary directory and removes
    it again -- so two actions cannot write over each other even where
    the build is not sandboxed. Within it, mypy's own output stays apart
    from what the venv rendered for the reason `mypy_cache._walk` gives.

    Returns:
        The working directory.
    """
    runfiles_dir = _runfiles_dir()
    if not runfiles_dir:
        raise RuntimeError(
            "A cache-producing mypy action has no runfiles tree. The venv "
            "must be built with `force_runfiles = True` so that paths "
            "recorded in the cache mean the same thing on every machine."
        )

    return Path(os.path.abspath(runfiles_dir))


def _repositories(cwd: Path) -> frozenset[str]:
    """The repositories the venv rendered, named as the tree names them.

    Two things want this list. `respell` needs it to tell a path in the
    workspace from one that came from another repository, every analyzed
    file being under one of these. `mypy_cache` needs it to step over
    them, nothing mypy writes landing in a directory named for a
    repository.

    Read before anything is put in the tree, which is the whole of why
    it can be read at all: once the caches are seeded, the directories
    here are a mixture of repositories and the module-named directories
    mypy's cache is laid out in, and nothing distinguishes them.
    """
    return frozenset(entry.name for entry in os.scandir(cwd) if entry.is_dir())


class _CacheRun(NamedTuple):
    """What `main` needs to drive a cache-producing run to completion."""

    cwd: Path
    args: list[str]
    before: frozenset[str]
    repositories: frozenset[str]


def _setup_cache_run(args: argparse.Namespace) -> _CacheRun:
    """Prepare a cached mypy run and change into its working directory.

    A target's dependencies arrive as stand-ins with cache entries behind
    them, to be found by import the way any other run would find them.
    Its own sources are here as files, and `mypy_modules.analyzed`
    decides which of them mypy is shown by name and which it is left to
    find by import.

    Returns:
        What the run needs afterwards: where it ran, what it was asked,
        what was in the working directory before it started, and which
        of the directories there are repositories.
    """
    # Settled first, while `os.path` can still say where things really
    # are.
    cwd = _working_dir()
    repositories = _repositories(cwd)
    mypy_paths.stop_absolutizing()

    # Under `--bazel` the cache lives in the working directory, so the
    # dependencies are seeded into the directory mypy will itself go
    # looking in -- the same one their stand-ins go to, that being where
    # the venv put the sources they replace. What lands there is what
    # they published, already settled at the answers their own actions
    # reached rather than the ones this action could reach for them.
    manifest = mypy_cache.merge_into(args.dep_caches, cwd)

    roots = _cached_paths(cwd, args.workspace_name)
    search_paths = [os.path.relpath(root, str(cwd)) for root in roots]

    # Ahead of every root, because a re-export answers to a name the
    # emptied source at that path already occupies.
    extra = mypy_modules.alternates(
        manifest, roots=roots, cwd=str(cwd), sources=args.sources
    )
    if extra:
        mypy_modules.stage_alternates(cwd / _SHIM_DIR, extra)
        search_paths.insert(0, _SHIM_DIR)

    config_file = mypy_options.generate_config(
        original_config=args.config_file,
        search_paths=search_paths,
        tmp_dir=cwd,
        silence_imports=True,
    )

    if args.stdlib:
        sources = [_write_probe(cwd, _stdlib_module_names())]
    else:
        sources, probed = mypy_modules.analyzed(
            args.sources,
            cwd=cwd,
            roots=roots,
            reported=not args.cache_only,
        )
        if probed:
            sources.append(_write_probe(cwd, probed))

    os.chdir(cwd)
    mypy_paths.relativize_sys_path(cwd)

    mypy_args = (
        ["--config-file", config_file.name]
        + (["-v"] if os.getenv(_DEBUG_ENV_VAR) else [])
        + mypy_options.cache_flags()
        + _typeshed_flags(cwd)
        + sources
    )

    # Last, once nothing else will be added: everything mypy is about to
    # write is whatever this does not already name.
    return _CacheRun(
        cwd, mypy_args, mypy_cache.snapshot(cwd, repositories), repositories
    )


def _setup_uncached_run(args: argparse.Namespace, tmp_dir: Path) -> list[str]:
    """Prepare a mypy run that builds no cache and inherits none.

    Returns:
        The mypy arguments.
    """
    config_file = mypy_options.generate_config(
        original_config=args.config_file,
        search_paths=_uncached_paths(args.workspace_root),
        tmp_dir=tmp_dir,
    )

    return [
        "--config-file",
        str(config_file),
        "--cache-dir",
        str(tmp_dir / "mypy_cache"),
        "--no-incremental",
        *(str(src) for src in args.sources),
    ]


def _parse_exit_code(code: int | str | None) -> int:
    """Normalize the code carried by the `SystemExit` mypy raises."""
    if code is None:
        return 0
    if isinstance(code, str):
        return int(code)
    return code


def _load_args() -> argparse.Namespace:
    """Parse arguments, reading them from a file when run as a test."""
    arg_file = os.environ.get("RULES_VENV_MYPY_RUNNER_ARGS_FILE")
    if "BAZEL_TEST" in os.environ and arg_file:
        content = _maybe_runfile(arg_file).read_text(encoding="utf-8")
        return parse_args(content.splitlines())
    return parse_args()


def _publish_cache(args: argparse.Namespace, run: _CacheRun, *, blocked: bool) -> None:
    """Write out only what this action added to the cache it was given.

    Runs before the move back to the execroot, because mypy's cache is
    found relative to the working directory.

    `run.before` is what `mypy_cache.snapshot` saw once the action had
    finished arranging the directory, so anything not in it is mypy's.
    That holds over a directory shared with the venv's own files because
    both walks step over the repositories those files are under, and
    everything else was already there when the snapshot was taken.

    Forwarding the whole accumulated cache would mean every consumer
    re-shipping its entire transitive closure, which is the cost this is
    meant to remove. Consumers instead take one small cache per
    transitive dependency, and because those are byte-reproducible the
    build cache holds one copy no matter how many consumers there are.

    What is published is settled at the answers this action reached, so
    that a consumer inherits those rather than reaching its own -- see
    `mypy_metadata`. Settling on the way out rather than on the way in
    means an entry is settled once, by the action that wrote it, instead
    of again in every action that goes on to inherit it.
    """
    if blocked:
        # Nothing here is trustworthy, and a manifest entry without a
        # matching cache entry is worse than no cache at all: the consumer
        # would stand an empty file in for a real module and quietly
        # believe it.
        args.cache_out.write_bytes(mypy_cache.pack({}, {}))
        return

    entries, paths = mypy_metadata.settled(
        mypy_cache.collect(run.cwd, run.repositories, run.before, _is_probe_entry)
    )
    args.cache_out.write_bytes(
        mypy_cache.pack(entries, mypy_metadata.covered(args.manifest, paths))
    )


def _mypy_ran(exit_code: int) -> bool:
    """Whether an exit code means mypy analyzed the sources and said so.

    mypy answers 0 when it found nothing and 1 when it found type errors,
    and both are verdicts. Every other code is not: 2 is mypy declining
    the run outright, and anything else at all -- a negative code from a
    signal, whatever a crash leaves behind -- is the analysis not having
    happened. Ordering the codes by size would make a failure mypy has no
    name for look milder than a type error, so they are told apart by
    what they mean rather than by which is larger.
    """
    return exit_code in (0, 1)


def _run_mypy(mypy_args: list[str], output: io.StringIO) -> int:
    """Run mypy once, reporting its exit code rather than exiting on it.

    Everything mypy says is collected rather than written through, so
    that the paths in it can be respelled before anyone reads them. Both
    of mypy's streams go to the same place, which is also what keeps them
    in the order mypy wrote them in.
    """
    try:
        mypy_main(args=mypy_args, stdout=output, stderr=output, clean_exit=True)
    except SystemExit as exc:
        return _parse_exit_code(exc.code)
    return 0


def _absolutize_outputs(args: argparse.Namespace, execroot: Path) -> None:
    """Pin output paths to the execroot before the working directory moves."""
    if args.marker and not args.marker.is_absolute():
        args.marker = execroot / args.marker
    if args.cache_out and not args.cache_out.is_absolute():
        args.cache_out = execroot / args.cache_out


def main() -> None:
    """Mypy test runner main entry point."""
    mypy_options.require_minimum_version()
    args = _load_args()

    # An action with a marker reports through its outputs rather than its
    # console, and a cache-only run in particular has diagnostics it has
    # already decided to disregard. Both hold their output back and print
    # it only if something goes wrong.
    quiet = bool(args.marker) or args.cache_only
    stream = io.StringIO()

    execroot = Path(os.getcwd())
    _absolutize_outputs(args, execroot)

    tmp_dir = Path(tempfile.mkdtemp(prefix="bazel-mypy-", dir=os.getenv("TEST_TMPDIR")))
    run: _CacheRun | None = None
    exit_code = 0

    blocked = False
    try:
        os.environ["HOME"] = str(tmp_dir)
        os.environ["USERPROFILE"] = str(tmp_dir)

        if args.cache_out:
            run = _setup_cache_run(args)
            exit_code = _run_mypy(run.args, stream)
        else:
            exit_code = _run_mypy(_setup_uncached_run(args, tmp_dir), stream)

        if args.cache_only and exit_code:
            # A cache-only run exists to publish type information, not to
            # judge it, and third-party code routinely does not check
            # clean, so type errors are dropped here.
            #
            # A run that reached no verdict at all is a different thing.
            # It has nothing to publish, and consumers have already been
            # told in Starlark that this target's sources are covered, so
            # they will leave them out and find the modules missing. That
            # is loud where it lands but says nothing about where it came
            # from, so the diagnostics are printed rather than dropped.
            blocked = not _mypy_ran(exit_code)
            exit_code = 0

    finally:
        if run:
            try:
                if exit_code == 0:
                    _publish_cache(args, run, blocked=blocked)
            finally:
                # Back even when writing the outputs failed, since what
                # is left to do is named from here. Nothing to clean: the
                # working directory is the venv's own temporary tree and
                # goes when the process wrapper takes that.
                os.chdir(execroot)
        if "TEST_TMPDIR" not in os.environ:
            shutil.rmtree(tmp_dir)

    output = mypy_paths.respell(
        stream.getvalue(),
        workspace=args.workspace_name,
        # Only a cached run reports paths this needs rewriting. A test
        # is run by Bazel from the workspace's own directory, so mypy has
        # already spelled everything the way the reader would.
        repositories=run.repositories if run else frozenset(),
    )
    if not quiet:
        print(output, end="", file=sys.stdout)
    elif exit_code != 0 or blocked or os.getenv(_DEBUG_ENV_VAR):
        if blocked:
            print(
                "mypy declined to analyze this target, so it publishes no "
                "types and anything importing it will not find its modules:",
                file=sys.stderr,
            )
        print(output, file=sys.stderr)
    if args.marker and exit_code == 0:
        args.marker.write_bytes(b"")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
