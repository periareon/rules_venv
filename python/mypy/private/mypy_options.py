"""What these rules ask of whatever mypy the toolchain supplies.

The mypy version is a workspace's to choose, so this is the one place
that reads it, decides which flags it can be asked for, and writes the
configuration every action runs under. Everything here answers to the
install rather than to the target being analyzed, which is what makes a
cache one action wrote readable by the next: mypy folds most of these
into the options snapshot it stores per module and abandons a cache
whose snapshot does not match the run reading it.

Nothing here is asked for on speed alone. An option that buys time at
some other cost is the workspace's to weigh, and it already has a place
to say so: the config file the toolchain names, which every action reads
and `generate_config` passes through untouched, so such an option stays
uniform across the build without these rules choosing it. mypy's
`native_parser` is the standing example. It is faster, and it is also
experimental, default-off upstream, and unable to read a source whose
encoding is declared the PEP 263 way rather than being UTF-8 -- on the
batched parse it hands the filename to `ast_serialize` and lets it
decode, which no coding declaration survives. A workspace that wants it
writes `native_parser = True`; one that has a single such file in its
closure is not made to find out the hard way.
"""

import configparser
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from mypy.version import __version__ as MYPY_VERSION

from python.mypy.private import mypy_metadata

# The oldest mypy these rules can share a cache across.
MINIMUM_VERSION = (2, 0)


def require_minimum_version() -> None:
    """Refuse a mypy too old to analyze a dependency once.

    These rules rest on mypy writing a module's cache from its interface
    alone and checking function bodies only where the errors are wanted,
    a split mypy grew in 2.0. Before it, every action that so much as
    imported a package type-checked the whole of it -- correct, and for a
    large dependency the difference between seconds and half an hour.
    Older releases are refused rather than tolerated because a version
    floor is a line in a requirements file where that is a week of not
    knowing why the build is slow.

    Raises:
        SystemExit: If the mypy the toolchain supplies predates 2.0.
    """
    try:
        version = tuple(int(part) for part in MYPY_VERSION.split(".")[:2])
    except ValueError:
        # A development build names itself something this cannot read.
        # Let it through: whoever is running one can see the version.
        return

    if version < MINIMUM_VERSION:
        minimum = ".".join(str(part) for part in MINIMUM_VERSION)
        sys.exit(
            f"rules_venv requires mypy {minimum} or newer, and the "
            f"`py_mypy_toolchain` in use supplies {MYPY_VERSION}. Older "
            "releases re-check every dependency in every target that "
            "imports it, which these rules are built not to do.",
        )


def cache_flags() -> list[str]:
    """The flags that make mypy's cache portable between actions.

    `--bazel` does most of it: it stops mypy absolutizing the paths it
    records, forces recorded mtimes to zero, and skips the size/hash
    validation that would otherwise reject the emptied dependency sources
    we hand it. It also pins the cache directory to the working
    directory, which is why the runner settles where it runs rather than
    naming a cache directory -- see `mypy_runner._working_dir`.

    `--no-sqlite-cache` settles where the cache lands, so that collecting
    it is reading files out of a directory rather than asking mypy. Which
    backend mypy would have picked has moved between releases and can be
    set from a workspace's config file, and the two disagree about more
    than speed: a database has to be opened through mypy's own API, which
    has itself changed shape. Naming the file-backed one keeps this to
    paths and bytes on both sides.

    Returns:
        The cache flags, less any the mypy in use does not have.
    """
    flags = ["--bazel", "--no-sqlite-cache"]

    # mypy packs a module's metadata into a binary form, which
    # `mypy_metadata` settles through mypy's own reader and which is both
    # smaller and faster than the JSON it replaced. Asking for JSON is the
    # fallback for an install with no such reader, where metadata that
    # cannot be settled would send a consumer back to a source it was
    # never given. Unlike the other two this is a cache-affecting option,
    # so it must be passed by every action or by none: it turns on the
    # mypy the toolchain supplies and never on the target.
    if not mypy_metadata.READS_FIXED_FORMAT:
        flags.append("--no-fixed-format-cache")

    return flags


def generate_config(
    original_config: Path,
    search_paths: Sequence[str],
    tmp_dir: Path,
    *,
    silence_imports: bool = False,
) -> Path:
    """Generate a copy of the mypy config, and point mypy at the venv.

    The search paths go through `MYPYPATH` rather than into the config's
    own `mypy_path`, because the config's is split on `,` and `:` on
    every platform: a Windows path is cut in half at its drive letter and
    the venv is never searched at all. `MYPYPATH` is split on
    `os.pathsep`, so it says the same thing everywhere, and mypy reads it
    ahead of whatever the config names, which is the order these were
    written in before.

    Path options a config can still carry (`plugins`, `files`, and the
    rest) resolve relative to the **working directory** rather than to
    the config file, so moving the config elsewhere is safe for those.
    The one exception is the `MYPY_CONFIG_FILE_DIR` variable mypy
    auto-sets to the config file's parent directory, which users
    reference in paths such as `mypy_path = $MYPY_CONFIG_FILE_DIR/stubs`.
    Moving the config would silently repoint those at wherever it was
    moved to, so this sets the variable back to where it came from.

    That answer is the config's directory as the execution root spells
    it, which a cached run then changes out from under by moving to the
    venv's tree, leaving such a reference naming a directory that is not
    there. Spelling it absolutely instead would be worse rather than
    better: an absolute `mypy_path` entry is recorded absolutely into
    every module reached through it, and a cache naming this machine's
    directories is one no other action can use.

    Args:
        original_config: Path to the user's mypy config file.
        search_paths: The venv's search paths, in the order mypy is to
            look in them.
        tmp_dir: Temporary directory for the generated config.
        silence_imports: Whether to judge only the sources named on the
            command line, leaving whatever they import unjudged.

    Returns:
        Path to the generated config file.
    """
    config = configparser.ConfigParser()
    config.read(str(original_config), encoding="utf-8")

    if not config.has_section("mypy"):
        config.add_section("mypy")

    if silence_imports:
        # A target is answerable for its own sources and no others. Every
        # dependency arrives here as a cache, and a cache mypy finds fresh
        # replays the errors recorded in it, so without this a target
        # fails over a type error somewhere in its transitive closure --
        # for third-party code, over a package nobody asked to have
        # checked. `silent` is mypy's own name for analyze-but-do-not-
        # report, and it applies to imported modules only: sources named
        # on the command line are still judged in full.
        #
        # Silencing also settles what a dependency costs. mypy checks the
        # bodies of a module's functions only where it might report on
        # them, so a module reached this way is analyzed to its interface
        # -- which is all a cache holds -- and no further.
        #
        # This is a cache-affecting option, so it has to be set the same
        # way in every action. It is, because every action reads the one
        # configuration file the toolchain names.
        config.set("mypy", "follow_imports", "silent")

        # `follow_imports` alone does not reach stubs: mypy exempts a
        # `.pyi` from it and analyzes the file as though it had been
        # named, unless told otherwise here. That exemption is wrong
        # twice over. It reports, so a target fails over a type error in
        # a dependency's stub -- the very thing the line above is for,
        # arriving by the one door it does not close. And it decides what
        # a cache is worth: mypy records on each module whether the run
        # that wrote it was silencing that module and refuses a silenced
        # cache to a run that is not silencing, so a consumer left
        # un-silencing a stub rejects everything it was given and reaches
        # for the emptied source behind it instead.
        #
        # Silencing a stub costs nothing that is not covered elsewhere:
        # the target that owns it names it, and a named source is judged
        # in full whatever this says.
        config.set("mypy", "follow_imports_for_stubs", "True")

    merged = tmp_dir / "mypy.ini"
    with open(merged, "w", encoding="utf-8") as f:
        config.write(f)

    os.environ["MYPYPATH"] = os.pathsep.join(search_paths)
    os.environ["MYPY_CONFIG_FILE_DIR"] = str(original_config.parent)
    return merged
