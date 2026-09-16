"""How a path becomes a module name, and back again.

mypy names a module after where its file sits below an import root, and
almost everything the runner does downstream turns on getting the same
answer mypy would. The rules are small but they are applied from several
directions -- to a target's own sources, to installed packages, to the
cache entries a previous run left behind, and once in reverse, to place
a file where mypy will read a given name off it -- so they live together
here rather than being restated at each one.

Deliberately has no dependencies, mypy's included. Nothing here needs to
resolve a module, only to name one.
"""

import keyword
import os
from collections.abc import Container, Iterable, Mapping, Sequence
from pathlib import Path

# The directory an installed package is found under. A file below one is
# reached by import rather than by being named, which is what decides how
# mypy treats it.
SITE_PACKAGES = "site-packages"

# What mypy reads a module out of, and so all a manifest entry or a
# directory listing can be standing in for.
SOURCE_SUFFIXES = (".py", ".pyi")


def under(path: str, root: str) -> bool:
    """Whether `path` is `root` or something below it, by name alone."""
    return path == root or path.startswith(root + os.sep)


def dotted_name(parts: Sequence[str]) -> str | None:
    """The module a path below an import root names, if it names one.

    A path that does not spell a name an `import` statement could carry
    is not importable at all, here or in any consumer, so there is
    nothing to be gained by analyzing it.

    Returns:
        The module name, or None if the path has no importable name.
    """
    tail = list(parts)
    if not tail:
        return None

    tail[-1] = tail[-1].rsplit(".", 1)[0]
    if tail[-1] == "__init__":
        tail.pop()

    # PEP 561 stub-only distributions ship their stubs in a directory
    # named for the package they describe plus a suffix.
    tail = [part.removesuffix("-stubs") for part in tail]
    if not tail or not all(
        part.isidentifier() and not keyword.iskeyword(part) for part in tail
    ):
        return None

    return ".".join(tail)


def installed_module(path: Path) -> str | None:
    """The name an installed file is importable under, if it has one.

    Only the part of the path below `site-packages` matters; that is
    where mypy stops when it works a module's name out, so the answer is
    the same in every action.

    Returns:
        The module name, or None if the path is not an installed module
        or has no importable name.
    """
    parts = path.parts
    found = [i for i, part in enumerate(parts) if part == SITE_PACKAGES]
    if not found:
        return None

    # The innermost one wins, since that is the one an import would have
    # resolved through.
    return dotted_name(parts[found[-1] + 1 :])


def entry_module(key: str) -> str:
    """The module a cache entry describes, read off the entry's own name.

    Entries are named for their module, laid out as a path and suffixed
    with which part of the module they hold, so the name up to the first
    dot is the module's own.
    """
    parts = key.split("/")
    parts[-1] = parts[-1].split(".", 1)[0]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def is_initializer(path: str) -> bool:
    """Whether a path names a package's `__init__`, whatever its suffix.

    Answers for a source and for a cache entry alike, both being named
    for the module they belong to and differing only after the first
    dot. The dot is part of the test, so a module named
    `__init__something` is not mistaken for one.
    """
    return os.path.basename(path).startswith("__init__.")


def _name_under(path: str, root: str) -> str | None:
    """The module a file below `root` would be named, if it names one."""
    return dotted_name(Path(os.path.relpath(path, root)).parts)


def published_name(path: str, roots: Sequence[str]) -> str | None:
    """The name a file is analyzed and cached under, given the roots in force.

    mypy names a file for the deepest search root it sits under, so this
    says the same: the roots arrive deepest first and the first one the
    file is below decides. That is the name the file's own package spells
    -- an `imports` root exists precisely to give it that name -- and so
    the name a consumer's import resolves to.

    It is not a name every action agrees on, because `imports` roots
    travel down the graph and a consumer may see a deeper one than the
    action that published the file did. Nothing here tries to make it
    one. The name is recorded in the cache's manifest by the action that
    used it, and a consumer arriving at some other name finds a stand-in
    that forwards to the published one.

    Args:
        path: The file to name.
        roots: The search roots, deepest first.

    Returns:
        The module name, or None if no root covers the path or the name
        it would take is not importable.
    """
    for root in roots:
        if under(path, root):
            return _name_under(path, root)
    return None


def analyzed(
    sources: Iterable[Path], *, cwd: Path, roots: Sequence[str], reported: bool
) -> tuple[list[str], list[str]]:
    """How each of an action's own sources is put in front of mypy.

    A file mypy is handed by name is one it reports on, and one whose
    cache it deletes again the moment it does: a module with an error in
    it is left uncached, so that a later run reaches it afresh and says
    the same thing rather than passing over it.

    That is right for an action whose errors are the point and wrong for
    one whose cache is. An action is exempted from reporting precisely
    because its sources do not check clean -- vendored code, mostly --
    which is the same condition mypy deletes the cache for, so naming
    those files would publish almost nothing. Consumers have already been
    told in Starlark that the files are covered and have left them out,
    so what they find is not a smaller cache but a missing module.

    Reaching a module by import instead makes it one of the imports the
    run follows, and a cached run silences those, so nothing is reported
    and nothing is deleted. What mypy infers is the same either way.

    Installed sources are imported however the action reports, for a
    reason of their own: naming one resolves it without the import search
    that decides what a consumer may see of it, and the two have to agree
    for a cache to carry across.

    Args:
        sources: The files the action was asked to analyze.
        cwd: Where mypy will run, which the named paths are relative to.
        roots: The search roots, deepest first, which is what decides
            the name a probed source is reached under.
        reported: Whether the action's diagnostics reach anyone.

    Returns:
        The paths to name, and the modules to reach by import.
    """
    named = []
    probed = []

    for source in sources:
        if SITE_PACKAGES in source.parts:
            # An installed file with no importable name is left out
            # entirely. No consumer can reach it either, so analyzing it
            # would only add this action's opinion of third-party code to
            # a cache nobody can use.
            installed = installed_module(source)
            if installed is not None:
                probed.append(installed)
            continue

        module = None if reported else published_name(str(source), roots)

        if module is None:
            # Everything a reporting action owns arrives here, that being
            # the point of reporting. So does a file with no importable
            # name, whoever is asking: there is no other way to reach it.
            named.append(os.path.relpath(os.path.abspath(source), cwd))
        else:
            probed.append(module)

    return named, probed


def alternates(
    manifest: Mapping[str, str],
    *,
    roots: Sequence[str],
    cwd: str,
    sources: Iterable[Path],
) -> dict[str, tuple[str, str]]:
    """Every name a covered source answers to besides its published one.

    A dependency's file was published under the name the roots in force
    where it was analyzed gave it. This action looks through its own set
    -- it inherits every root its dependencies declare and adds whatever
    it declares itself -- so the same file is routinely reachable here
    under a name its cache is not keyed by. Something has to stand at
    each of those, or the import finds the stand-in written in place of
    the pruned source and reads an empty module out of it.

    The manifest is what this is worked out from rather than the
    directories themselves. It is the exact list of files whose sources
    are gone, it already says what each was published as, and it spares a
    walk of every root in the closure.

    Names already spoken for are left alone, and so are names that would
    have to sit inside one. A name some cache publishes is answered by
    the file behind it, and a name this action's own sources take is
    answered by the source; staging either, or a package containing
    either, would shadow the real thing, since what is staged is
    searched first and stands as a package all the way down.

    Args:
        manifest: Each covered source, against its published module.
        roots: The search roots, deepest first.
        cwd: Where mypy runs, which is also where the manifest's entries
            are rooted.
        sources: The files this action analyzes itself.

    Returns:
        Each extra name, against the module it forwards to and the
        manifest entry it stands for.
    """
    reserved = set(manifest.values())
    reserved.update(
        name
        for name in (published_name(str(source), roots) for source in sources)
        if name
    )

    # Each root as the manifest spells its entries: relative to where
    # mypy runs, separated by `/`, and ending in one so that it only
    # matches whole components. That directory itself comes out as the
    # empty prefix, which every entry is under, and a root outside it as
    # none at all. Working in this spelling rather than joining and
    # relativizing every entry against every root is what keeps a closure
    # of tens of thousands of pairs down to a string comparison each.
    prefixes = []
    for root in roots:
        relative = os.path.relpath(root, cwd)
        if relative == os.curdir:
            prefixes.append("")
        elif not relative.startswith(os.pardir):
            prefixes.append(relative.replace(os.sep, "/") + "/")

    extra: dict[str, tuple[str, str]] = {}
    for entry, module in sorted(manifest.items()):
        if not module:
            continue
        for prefix in prefixes:
            if not entry.startswith(prefix):
                continue
            name = dotted_name(entry[len(prefix) :].split("/"))
            if name and not _spoken_for(name, reserved):
                extra.setdefault(name, (module, entry))
    return extra


def _spoken_for(name: str, reserved: Container[str]) -> bool:
    """Whether `name`, or a package it would sit inside, is taken."""
    parts = name.split(".")
    return any(".".join(parts[: index + 1]) in reserved for index in range(len(parts)))


def stage_alternates(root: Path, names: Mapping[str, tuple[str, str]]) -> None:
    """Write a module at each extra name that re-exports the published one.

    One file carries one name per run -- mypy refuses outright to reach
    the same file under two module names -- so the extra name needs a
    file of its own. A copy of the source would be the obvious one, but
    it would be a second definition of everything the original defines,
    two classes that are not the same class, and its own imports would
    have to resolve all over again. A re-export defines nothing: whatever
    the published module says a name means, this says the same, and says
    it by pointing at the cache entry the owning action already wrote.

    A package also names each of its own staged submodules. A star import
    carries what the published module defines, and a submodule is not
    something a package defines -- it becomes an attribute of the package
    only because something imported it, and what did the importing was
    another action. Naming them with `as` says so again here, in the form
    `no_implicit_reexport` accepts, which is what keeps `pkg.sub`
    reachable from a target that only wrote `import pkg`.

    Each one goes at the path its own name spells: mypy serializes a
    module's path into its data and takes the interface hash over those
    bytes, so a location that varied by target would leave one target's
    idea of a module unable to match the next one's.

    What a re-export answers to is a name the file behind it already
    occupies -- the stand-in is at the path the deeper root spells -- so
    the caller has to put this tree ahead of the roots it searches, or a
    root searched first hands mypy the emptied source instead.

    Search order is not enough on its own, which is why the directories
    along the way are made into packages. A Bazel tree has no
    `__init__.py` in it, so a name spelled out of one is only ever a
    namespace package, and mypy prefers a candidate whose packages it can
    verify to one it cannot whatever the search order says -- which would
    leave the emptied source winning the name the re-export exists to
    answer. `alternates` has already established that nothing real
    answers to any of these, so an empty package is a faithful account of
    what is there.
    """
    submodules: dict[str, list[str]] = {}
    for name in names:
        parent, _, child = name.rpartition(".")
        if parent:
            submodules.setdefault(parent, []).append(child)

    for name, (module, entry) in names.items():
        parts = name.split(".")
        lines = [f"from {module} import *\n"]
        if is_initializer(entry):
            parts.append("__init__")
            lines += [
                f"from . import {child} as {child}\n"
                for child in sorted(submodules.get(name, ()))
            ]
        dest = root.joinpath(*parts).with_suffix(os.path.splitext(entry)[1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("".join(lines), encoding="utf-8")

    initializers = {f"__init__{suffix}" for suffix in SOURCE_SUFFIXES}
    for directory, _, filenames in os.walk(root):
        if directory != str(root) and initializers.isdisjoint(filenames):
            Path(directory, "__init__.py").touch()
