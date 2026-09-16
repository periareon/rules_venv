"""The paths mypy records, and the paths mypy reports.

mypy writes a module's path into that module's cache data and takes the
interface hash over those bytes, so two actions analyzing the same file
must record the same path for it or neither can use the other's work.
Every action runs somewhere different -- a fresh temporary venv, a
sandbox, a remote worker, an unsandboxed machine -- so left alone mypy
records a name no other action will ever produce.

`stop_absolutizing` and `relativize_sys_path` take the absolute spelling
out of what mypy sees: one out of `os.path`, one out of the interpreter's
import roots. They act on the process rather than on a file, which is why
they sit apart from the code arranging the directory they are settling.

What that leaves is a path that means the same thing in every action and
nothing to the person reading it. `respell` puts the reader's spelling
back, and does it to the output alone, after everything that was going to
be hashed has been.
"""

import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from python.mypy.private import mypy_modules


def stop_absolutizing() -> None:
    """Stop `os.path` absolutizing, so mypy records portable paths.

    Under `--bazel` mypy names a file by `os.path.relpath`, which would be
    enough on its own. But the module finder absolutizes every search path
    before it looks in one, so a module reached by import -- typeshed's
    stubs above all -- is named from the root of the filesystem, and the
    venv's directory is a fresh temporary one on every run.

    mypy is compiled with mypyc, so its intra-module calls are statically
    bound and cannot be intercepted, but `os.path` is a different module
    and so is still looked up at call time, including after mypy has been
    imported.

    `relpath` has to be replaced alongside `abspath` because it resolves
    `abspath` through its own module globals and would otherwise inherit
    the neutered version.

    What replaces `abspath` spells a relative path from the working
    directory, keeping the leading `./`. Either spelling would do -- what
    matters is that every action picks the same one, since the answer
    reaches the options snapshot mypy stores per module and so the
    published bytes. Changing it is therefore a cache invalidation, not a
    cosmetic edit.

    `commonpath` is replaced to keep it in that spelling. It drops `.`
    components, so a common ancestor of two paths would come back spelled
    differently from the paths it was derived from, and mypy compares the
    two for equality -- which is how it recognizes typeshed. Answering
    through `abspath` settles that whichever spelling is in force.
    """
    real_abspath = os.path.abspath
    real_relpath = os.path.relpath
    real_commonpath = os.path.commonpath

    def abspath(path: str) -> str:
        # `normpath` alone is what the real `abspath` does minus the join
        # against the working directory. The empty path is the one case
        # where that join is the whole answer, and `.` is what the real
        # one would reduce to here -- spelled out because mypy passes it.
        if not path:
            return os.curdir
        normalized = os.path.normpath(path)
        if os.path.isabs(normalized):
            return normalized
        return os.path.join(os.curdir, normalized)

    def relpath(path: str, start: str = os.curdir) -> str:
        return real_relpath(real_abspath(path), real_abspath(start))

    def commonpath(paths: Iterable[str]) -> str:
        # Two relative paths with nothing in common leave the real one
        # returning the empty string. `.` is what that means here, and
        # is what `abspath` would have said, so say it too.
        return abspath(real_commonpath(paths))

    # `os.path` is an alias for the platform module (posixpath/ntpath), so
    # this covers both names.
    os.path.abspath = abspath  # type: ignore[assignment]
    os.path.relpath = relpath  # type: ignore[assignment]
    os.path.commonpath = commonpath  # type: ignore[assignment]


def relativize_sys_path(cwd: Path) -> None:
    """Name the venv's import roots relative to the working directory.

    mypy asks the running interpreter for its search directories and looks
    there for anything the workspace itself does not supply -- packages
    from other Bazel repositories, third-party distributions, the venv's
    own site-packages. Those entries are absolute and run through the
    venv's temporary directory, whose name is new on every run, so a
    module found through one is recorded under a name no other action will
    ever produce, and no consumer finds it fresh again.

    Naming them relative to the directory mypy is about to work in gives
    every action the same name for the same file. Imports keep working
    because a relative `sys.path` entry is resolved against the working
    directory each time it is searched, and by here that directory is
    settled.

    Only entries inside the venv are rewritten. Anything else is outside
    this run's control and is left to speak for itself. The venv is what
    the working directory sits in rather than the working directory
    itself -- the interpreter and the rendered runfiles tree are
    siblings -- so it is the parent that decides what belongs to this
    run.
    """
    root = str(cwd.parent)
    for index, entry in enumerate(sys.path):
        if not os.path.isabs(entry):
            continue
        if not mypy_modules.under(entry, root):
            continue
        sys.path[index] = os.path.relpath(entry, cwd)


def respell(text: str, *, workspace: str, repositories: Iterable[str]) -> str:
    """Name the paths in what mypy said the way the reader would name them.

    mypy already takes the working directory off the front of every path
    it reports, so what arrives here is a file's rlocationpath: the
    repository's name followed by the path within it. A cached run gets
    there by working in the runfiles tree, and `py_mypy_test` by being a
    test, which Bazel runs from the workspace's directory in its own
    runfiles tree -- which is why the latter passes no repositories and
    leaves this with nothing to do.

    The workspace's own name comes off, because nobody spells their own
    repository's name when talking about a file in it, and what is left
    is what mypy would have said had it run at the root of the
    repository -- which is where it runs by hand, and so what anything
    reading its output expects.

    Any other repository keeps its name and gains a `../`, which says
    the same thing about it that the stripped workspace name says about
    the rest: the file is outside the repository the reader is standing
    in. It is also true as written, the repositories being siblings in
    the tree mypy ran in.

    Names are replaced wherever they appear rather than at the head of a
    line, because mypy puts a path mid-message when it reports a
    duplicate module or a source file found under two names. One pass
    over the text does every name at once, so no rewrite can land on the
    output of another, and a name already following a separator or a dot
    is passed over -- that is a path mypy built itself rather than one
    it is reporting, and it is already relative to somewhere.

    Args:
        text: What mypy said.
        workspace: The name of the workspace's repository within it.
        repositories: Every repository in the tree mypy ran in, the
            workspace included, or nothing to leave the text alone.

    Returns:
        The same text, with every path in it named from the root of the
        repository it belongs to.
    """
    names = sorted(repositories)
    if not names:
        return text

    # A name is followed by a separator, so no name can be a prefix of
    # another as matched here and the order of the alternation does not
    # decide anything. Sorted only to keep the pattern stable.
    pattern = re.compile(
        r"(?<![\w./\\-])(" + "|".join(re.escape(name) for name in names) + r")[/\\]"
    )

    def replace(match: re.Match[str]) -> str:
        if match.group(1) == workspace:
            return ""
        return os.pardir + os.sep + match.group(0)

    return pattern.sub(replace, text)
