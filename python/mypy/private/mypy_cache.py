"""The cache artifact passed between Mypy actions.

An action publishes what it learned about its own sources so the actions
downstream do not have to be given those sources at all. This module owns
the artifact those entries travel in, and the directory operations that
move a cache into mypy's working directory and read the next one back
out of it.

An entry's key is the path of a file mypy left in its working directory
and the value is that file's bytes, so a cache crosses an action boundary
as mypy wrote it. No mypy API is called, and the only thing read off an
entry's name is which module it belongs to -- a rule `mypy_modules`
owns -- so a release that renames its cache files or adds another one per
module needs no change here. What one of those files says is
`mypy_metadata`'s business, and the runner settles the entries through it
on the way out.

Travelling beside the entries is the manifest: the sources they stand in
for, each one paired with the module name it was published under. A
consumer cannot work that name out for itself -- it depends on the import
roots that were in force where the file was analyzed -- so the action
that did the analyzing says it here.
"""

import os
import struct
import zlib
from collections.abc import (
    Callable,
    Container,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from collections.abc import Set as AbstractSet
from pathlib import Path

from python.mypy.private import mypy_modules

# Artifact format for the caches passed between actions. Whatever mypy
# leaves on disk is a poor thing to ship -- the serialized data
# compresses by roughly an order of magnitude -- so the files are
# gathered into this format, which is nothing more than a bag of opaque
# blobs plus the manifest naming the sources they stand in for.
#
# It is a flat concatenation under one zlib stream rather than a `tar`
# because it is read once per transitive dependency: a consumer with six
# hundred of them spends about four hundred milliseconds here, where
# `tarfile` costs several seconds to parse the same bytes. The formats
# are otherwise the same size and hold the same thing.
#
# Cache and manifest share one file so that a consumer takes a single
# input per transitive dependency rather than a pair.
#
# Carries no version. This module is an input to every action that reads
# one of these, so a change to the format already invalidates every cache
# in the build and there is never an old one to recognize.
_CONTAINER_MAGIC = b"rules_venv/mypy-cache\n"

# zlib rather than gzip because the gzip header carries a timestamp, and
# these artifacts have to be byte-reproducible.
_CONTAINER_LEVEL = 6

# The one header the format is made of. The body is a pair of counts
# followed by that many counted pairs of strings, so a pair of `u32`
# describes both and one struct suffices.
_PAIR = struct.Struct("<II")


def _walk(root: Path, repositories: AbstractSet[str]) -> Iterator[str]:
    """Every file below `root` bar the repositories, named relative to it.

    A cache is written by one action and read by another, and the two
    need not run on the same operating system: a Windows host can be
    served a cache a Linux machine put in the remote cache, and the
    artifact has to be byte-identical either way for that to happen at
    all. So the separator in an entry's name is fixed here rather than
    left to whichever host did the walking. `_prepare` reads them back
    through `pathlib`, which accepts `/` on both.

    The repositories the venv rendered are stepped over, which on a
    measured action is two files in five: every source in the closure is
    under one, and so is the stand-in for every source that was pruned.
    Nothing mypy writes lands in one, a cache entry being named for its
    module and a repository not being a name a module takes -- the same
    thing `mypy_runner._working_dir` rests on when it settles mypy here
    at all.
    """
    prefix = len(str(root)) + 1
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath == str(root):
            dirnames[:] = [name for name in dirnames if name not in repositories]
        # `os.walk` descends from `root`, so every directory it reports is
        # already spelled as `root` plus a separator plus the rest.
        directory = dirpath[prefix:].replace(os.sep, "/")
        for name in filenames:
            yield f"{directory}/{name}" if directory else name


def snapshot(root: Path, repositories: AbstractSet[str]) -> frozenset[str]:
    """Record what is in mypy's working directory before mypy runs.

    mypy works in the venv's own tree, so what this records is what the
    action put beside the repositories `_walk` steps over -- the
    generated config, the probe, the staged re-exports, the seeded
    dependency caches. All of it is in place by the time this runs, so
    whatever appears afterwards is mypy's cache and nothing else. This is
    what lets the cache be collected without knowing a single one of
    mypy's file names, which is the one thing about the cache that has
    actually changed between releases.

    Names are enough. An inherited entry mypy chose to rewrite still
    belongs to the dependency that published it, and republishing it here
    would put the same module in two caches.
    """
    return frozenset(_walk(root, repositories))


def collect(
    root: Path,
    repositories: AbstractSet[str],
    before: Container[str],
    skip: Callable[[str], bool],
) -> dict[str, bytes]:
    """Read the cache files mypy added to its working directory.

    Steps over the same directories `snapshot` did, so that the two
    describe the same tree and their difference is what mypy wrote.

    `skip` is consulted on the name alone, before the file is read.
    """
    entries: dict[str, bytes] = {}
    for name in _walk(root, repositories):
        if name in before or skip(name):
            continue
        entries[name] = (root / name).read_bytes()
    return entries


def _prepare(root: Path, name: str, made: set[Path]) -> Path:
    """Where `name` goes below `root`, its directory already created.

    `made` carries the directories seen so far. A cache of a few thousand
    entries covers a few hundred directories, so most names arrive at one
    that has already been made.
    """
    path = root.joinpath(name)
    parent = path.parent
    if parent not in made:
        parent.mkdir(parents=True, exist_ok=True)
        made.add(parent)
    return path


def _stand_in(path: Path) -> None:
    """Put an empty file where `path` is, unless something is there.

    Exclusive rather than a plain truncating open, because what may
    already be there is a real source: a path can be both an input and a
    manifest entry when a dependency is checked from source, and mypy
    will read whichever of the two it finds.
    """
    try:
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL))
    except FileExistsError:
        pass


def _materialize(paths: Iterable[str], root: Path, made: set[Path]) -> None:
    """Create empty stand-ins for the sources a cache replaces.

    mypy resolves a module by finding a file for it, and only then looks
    in the cache, so a dependency cannot be dropped outright -- but the
    file it finds may be empty, since under `--bazel` the cached entry is
    accepted without comparing size or hash. PEP 561 is checked during
    that same resolution step, which is why `py.typed` markers have to be
    listed in the manifest alongside the modules they cover.

    `root` is the venv's runfiles tree, which is also where mypy runs.
    The wrapper builds that tree one file at a time, so every directory
    in it is a real directory and writing into one cannot escape into the
    read-only execution root.
    """
    for name in paths:
        _stand_in(_prepare(root, name, made))


def _mark_packages(packages: AbstractSet[str], root: Path) -> None:
    """Let the cache tree answer for the packages whose entries it holds.

    `--bazel` pins mypy's cache directory to the working directory, which
    is also one of the places mypy looks for modules. A cache tree is
    therefore a tree of package-named directories sitting somewhere that
    is searched for packages -- harmless except for a package no
    directory can prove it is. A namespace package has no `__init__`, so
    mypy cannot prefer the real one and falls back on taking the first
    directory of that name on the search path. The working directory
    comes first, so the cache tree wins and the package resolves to a
    directory with no modules in it.

    What follows is worse than the missing package. mypy looks for the
    package's cache under the name it gives a directory rather than an
    `__init__`, finds nothing, and analyzes the package as new -- so
    every module that named it is stale and is re-read from the empty
    stand-in the pruning left. A consumer sees a module with no members
    and reports on every name imported from it.

    The `__init__` written here is what the directory is missing: with
    one, the cache tree names itself the package it already holds the
    entries for, mypy asks for the cache under the name those entries
    have, and the answer is the one the dependency published. Nothing
    reads the file, a cache mypy finds fresh being the whole of what it
    knows about that module.

    Only a package under a namespace package gets one, that being the
    only kind reachable this way. A package whose parents all have an
    `__init__` is a match mypy prefers outright rather than a tie it
    breaks by order, so it goes on resolving to the file it came from.

    Args:
        packages: The cache tree's package directories, relative to
            `root`.
        root: mypy's working directory.
    """
    for package in packages:
        # Every ancestor is a prefix ending where a separator does, which
        # is what the set is keyed by. A top-level package has none, and
        # so is skipped: the cache tree standing in for one of those is
        # harmless, since the package mypy would have found instead has
        # no members either.
        ancestors = (package[:cut] for cut, char in enumerate(package) if char == "/")
        if all(ancestor in packages for ancestor in ancestors):
            continue
        marker = root.joinpath(package, "__init__.pyi")
        _stand_in(marker)
        os.utime(marker, (0, 0))


def _seed(
    entries: Mapping[str, bytes], root: Path, made: set[Path], packages: set[str]
) -> None:
    """Write dependency cache files into mypy's working directory.

    The mtime is set to zero to match what mypy records under `--bazel`.
    mypy compares a data file's mtime on disk against the one named in
    the metadata beside it, so a file restored carrying the time it was
    written is rejected and the module analyzed over again -- silently,
    since a cache miss is not an error.

    `packages` collects the directories holding a package's own entries,
    which `_mark_packages` needs once every cache has been read. They are
    noted here rather than worked out afterwards because the names are
    already in hand, and there are tens of thousands of them across a
    large closure.
    """
    for name, data in sorted(entries.items()):
        path = _prepare(root, name, made)
        path.write_bytes(data)
        os.utime(path, (0, 0))
        # A module's entries are named for the module, so a package's are
        # named for its `__init__`, and the directory one sits in is the
        # package.
        if mypy_modules.is_initializer(name):
            packages.add(name.rpartition("/")[0])


def _append_pair(body: list[bytes], first: bytes, second: bytes) -> None:
    """Add one counted pair of strings to the body being built."""
    body.append(_PAIR.pack(len(first), len(second)))
    body.append(first)
    body.append(second)


def _read_pair(body: bytes, offset: int) -> tuple[bytes, bytes, int]:
    """Read one counted pair of strings, and say where the next one starts."""
    first_len, second_len = _PAIR.unpack_from(body, offset)
    offset += _PAIR.size
    first = body[offset : offset + first_len]
    offset += first_len
    second = body[offset : offset + second_len]
    return first, second, offset + second_len


def pack(entries: Mapping[str, bytes], manifest: Mapping[str, str]) -> bytes:
    """Serialize cache entries and their manifest to the artifact format."""
    body = [_PAIR.pack(len(entries), len(manifest))]
    for key, value in sorted(entries.items()):
        _append_pair(body, key.encode("utf-8"), value)
    for path, module in sorted(manifest.items()):
        _append_pair(body, path.encode("utf-8"), module.encode("utf-8"))
    return _CONTAINER_MAGIC + zlib.compress(b"".join(body), _CONTAINER_LEVEL)


def unpack(path: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Read cache entries and their manifest out of the artifact format."""
    blob = path.read_bytes()
    if not blob.startswith(_CONTAINER_MAGIC):
        raise ValueError(f"Not a mypy cache artifact: {path}")

    body = zlib.decompress(blob[len(_CONTAINER_MAGIC) :])
    entry_count, path_count = _PAIR.unpack_from(body)
    offset = _PAIR.size

    entries: dict[str, bytes] = {}
    for _ in range(entry_count):
        key, value, offset = _read_pair(body, offset)
        entries[key.decode("utf-8")] = value

    manifest: dict[str, str] = {}
    for _ in range(path_count):
        source, module, offset = _read_pair(body, offset)
        manifest[source.decode("utf-8")] = module.decode("utf-8")

    return entries, manifest


def merge_into(sources: Sequence[Path], root: Path) -> dict[str, str]:
    """Seed mypy's working directory from the dependency caches.

    Everything a cache brings lands here: the entries mypy will read, the
    package markers that let it find them, and an empty stand-in for each
    source the entries were published in place of.

    A module no cache upstream had claimed yet is published by whichever
    action first reached it, and several may reach it independently, so
    the same key can arrive from more than one cache. The copies describe
    the same interface -- every action names every file the same way, so
    they have to -- but they can still differ in the metadata recording
    how the module was reached, most often whether it was analyzed as a
    named source or followed into from an import.

    Sorting the caches settles which copy wins without depending on the
    order the build happened to list them in, and a module's entries
    always travel together in one cache, so nothing ends up taking its
    interface from one copy and its metadata from another. Writing each
    one out before the next is read gives the same result as merging
    first and writing after -- a later cache overwrites an earlier copy
    either way -- while holding one dependency in memory rather than the
    whole closure, which for a target with six hundred of them is the
    difference between a few megabytes and a few hundred.

    Args:
        sources: The dependency caches to read.
        root: mypy's working directory, where the entries go.

    Returns:
        The source paths those caches stand in for, each against the
        module name it was published under.
    """
    made: set[Path] = set()
    manifest: dict[str, str] = {}
    packages: set[str] = set()
    for source in sorted(sources):
        entries, source_manifest = unpack(source)
        _seed(entries, root, made, packages)
        manifest.update(source_manifest)

    # Last, because whether a package needs marking depends on which of
    # its parents any of the caches published, and no cache can answer
    # for another.
    _mark_packages(packages, root)
    _materialize(manifest, root, made)
    return manifest
