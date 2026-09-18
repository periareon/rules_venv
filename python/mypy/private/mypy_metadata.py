"""What a dependency's metadata has to say before another action reads it.

mypy records the imports it could not resolve, and reanalyzes a module as
soon as one of them resolves after all -- a name that was nothing may now
be a package, and the module's types would change. Within one build that
is exactly right. Across actions it is not: whichever action reached a
module first saw only its own dependencies, and every consumer sees those
plus its own, so an optional import the first one had no reason to carry
is routinely present downstream.

The consumer then reanalyzes, and that needs the source, which is the one
thing a cached dependency exists not to ship. What it finds in its place
is the stand-in, which parses as an empty module, so every name the
consumer wanted is gone -- and since reanalysis changes the module's
interface, so is everything that depended on it. That is how a single
optional import in some third-party package empties out a first-party
target several levels away.

Dropping the record settles the module at what its own action concluded:
a name that action could not resolve stays unresolved in every consumer,
which is what the published interface already says and the only answer
that does not turn on which action got there first.

The other thing the metadata answers is which modules are in a cache at
all, which is not the same as which ones the action set out to publish.
That is `covered`, and it turns on the same stand-in: a file claimed with
nothing behind it empties out the same way an unsettled one does.

This is the only thing anywhere that looks inside a cache file, and it
borrows mypy's own reader and writer wherever there is one to borrow.
The metadata is versioned, has gained fields across the releases
supported here, and from mypy 2.0 is written in a packed binary form that
is mypy's business alone. Keeping the one place that needs to understand
it separate is what leaves `mypy_cache` a bag of opaque bytes.
"""

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath

from python.mypy.private import mypy_modules

try:
    from mypy.cache import CacheMeta, CacheMetaEx, ReadBuffer, WriteBuffer

    # Whether the packed form can be settled, and so whether mypy may be
    # left to write it. `mypy_options.cache_flags` asks for the JSON form
    # where this is False, because metadata that cannot be settled sends
    # a consumer back to a source it was not given.
    READS_FIXED_FORMAT = True
except ImportError:  # pragma: no cover - depends on the mypy in use
    READS_FIXED_FORMAT = False

# How many bytes of format version mypy writes ahead of a module's
# packed metadata and checks before reading it back. They are sliced off
# before mypy's reader is handed the rest and put back unchanged: the
# check is mypy's, and answering it is not this module's business.
_FF_PREFIX = 2

# What an entry holding metadata is named. mypy lays a module's cache out
# as `<module>.<part>.<format>`, splitting off the part of the metadata
# that describes indirect imports into a file of its own.
_JSON_META = ".meta.json"
_JSON_META_EX = ".meta_ex.json"
_FF_META = ".meta.ff"
_FF_META_EX = ".meta_ex.ff"

# The lists carrying one value per import the module named, the ones it
# resolved first and the ones it could not after them.
_PER_IMPORT = ("dep_prios", "dep_lines")


def covered(manifest: Iterable[str], paths: Mapping[str, str]) -> dict[str, str]:
    """The manifest entries a cache really does stand in for, and as what.

    An action is told which files it covers before it runs, and mypy
    does not necessarily leave a cache for all of them: a module it
    reported an error in has its cache files deleted again on the way
    out, so that a later run reaches the module afresh and says the same
    thing rather than passing over it. What the action publishes is
    therefore not always what it was told to claim.

    A claim with nothing behind it is worse than no cache at all. The
    consumer drops the source for the empty stand-in and then has
    nothing to read the module's types from, so every name it defined
    goes missing, several targets away from anything that looks wrong.
    Where that bites is a dependency analyzed only for its cache: a
    target is exempted from reporting precisely because it does not pass
    -- vendored code, mostly -- which is the same condition mypy throws
    the cache away for, so almost none of what it claimed would be
    backed by anything.

    Each kept source is recorded against the module name it went into the
    cache under, which is read off the entry that holds it rather than
    worked out from the path. A consumer has no way to work it out: the
    name depends on which import roots were in force where the file was
    analyzed, and a consumer reaching the same file may well be looking
    through a different set. Being told means a stand-in can say what it
    stands for -- see `mypy_cache.merge_into` -- so a consumer that
    resolves the file under some other name still lands on what was
    published.

    Sources are matched without their extension, so a `.py` still counts
    as covered by the `.pyi` analyzed in its place.

    Two kinds of entry stay as they came, recorded against no module. One
    is anything that is not a source: no cache entry ever stood in for
    one, and what does is the caller's own argument that mypy never opens
    it. The other is an installed source, for the same reason one step
    removed -- PEP 561 decides whether mypy may read an installed package
    at all, and when it declines there is no cache to expect and the
    stand-ins are the only thing left making the package findable.
    Dropping those turns an untyped dependency from one mypy knows about
    and passes over into one it cannot find.

    Both sides are already spelled the same way. mypy runs in the venv's
    own tree, so a path it recorded is relative to the same directory the
    manifest's rlocationpaths are, and the two compare directly once
    `normpath` has taken off the leading `./` mypy writes.

    Args:
        manifest: The entries claimed, as rlocationpaths.
        paths: Each cache entry holding metadata, against the source path
            it records, as `settled` read them.

    Returns:
        The entries to record, each against the module it was published
        as, or against nothing where no module stands behind it.
    """
    analyzed: dict[str, str] = {}
    for name, path in paths.items():
        stem = os.path.splitext(os.path.normpath(path))[0]
        analyzed[stem] = mypy_modules.entry_module(name)

    published: dict[str, str] = {}
    for entry in manifest:
        stem, extension = os.path.splitext(entry)
        if (
            extension not in mypy_modules.SOURCE_SUFFIXES
            or mypy_modules.SITE_PACKAGES in PurePosixPath(entry).parts
        ):
            published[entry] = ""
            continue

        module = analyzed.get(os.path.normpath(stem))
        if module is not None:
            published[entry] = module

    return published


def settled(entries: Mapping[str, bytes]) -> tuple[dict[str, bytes], dict[str, str]]:
    """The entries of a dependency's cache as a consumer has to see them.

    Everything but a module's metadata is passed through on the strength
    of its name, which is also what keeps seeding hundreds of
    dependencies cheap: the data files are the bulk of a cache and none
    of them is read.

    The source each module was analyzed from comes back alongside,
    because it is written in the metadata this has already had to parse
    and `covered` would otherwise parse every one of them a second time.
    It is read off the metadata rather than derived from the entry's
    name, which is mypy's own arrangement of module names into paths and
    not something to reimplement.

    Returns:
        The entries, with each module settled at what its own action
        concluded about the imports it could not resolve, and the source
        path recorded by each entry that records one.
    """
    kept: dict[str, bytes] = {}
    paths: dict[str, str] = {}
    for name, data in entries.items():
        kept[name], path = _settle(name, data)
        if path:
            paths[name] = path
    return kept, paths


def _settle(name: str, data: bytes) -> tuple[bytes, str | None]:
    """One entry, settled if it is metadata and left alone if it is not.

    Only a module's primary metadata names a source. The second file
    holds what did not fit in the first and is settled for its own sake.
    """
    if name.endswith(_JSON_META):
        return _settle_json(data)
    if name.endswith(_JSON_META_EX):
        return _settle_json(data)[0], None
    if READS_FIXED_FORMAT:
        if name.endswith(_FF_META):
            return _settle_packed(data)
        if name.endswith(_FF_META_EX):
            return _settle_packed_ex(data), None
    return data, None


def _settle_packed(data: bytes) -> tuple[bytes, str | None]:
    """A module's packed metadata, read and rewritten by mypy's own code."""
    # The path of the data file beside this one is not part of what was
    # written: mypy derives it from the module's name and supplies it on
    # every read. Whatever is passed here is therefore never stored.
    meta = CacheMeta.read(ReadBuffer(data[_FF_PREFIX:]), "")
    if meta is None:
        return data, None
    if not meta.suppressed:
        return data, meta.path

    resolved = len(meta.dependencies)
    if any(
        len(value) != resolved + len(meta.suppressed)
        for value in (meta.dep_prios, meta.dep_lines)
    ):
        # Metadata whose lists this cannot account for is left exactly as
        # it came. The module may be reanalyzed, but that is what happens
        # without any of this, not something done to it here.
        return data, meta.path

    meta.suppressed = []
    # The resolved imports come first in each list, so the tail is what
    # the dropped ones accounted for.
    meta.dep_prios = meta.dep_prios[:resolved]
    meta.dep_lines = meta.dep_lines[:resolved]
    # Recorded so a consumer can tell the imports were left unresolved
    # under the same settings it is using. With none left unresolved
    # there is nothing for it to disagree with.
    meta.suppressed_deps_opts = b""

    written = WriteBuffer()
    meta.write(written)
    return data[:_FF_PREFIX] + written.getvalue(), meta.path


def _settle_packed_ex(data: bytes) -> bytes:
    """The second metadata file, which carries no lists to keep in step."""
    meta_ex = CacheMetaEx.read(ReadBuffer(data))
    if meta_ex is None or not meta_ex.suppressed:
        return data

    meta_ex.suppressed = []

    written = WriteBuffer()
    meta_ex.write(written)
    return written.getvalue()


def _settle_json(data: bytes) -> tuple[bytes, str | None]:
    """Metadata from a mypy writing the older JSON form.

    Every release these rules accept packs the metadata instead, so this
    is reached only where `mypy.cache` will not import and `cache_flags`
    has therefore asked for JSON. Settling it is still worth doing: the
    alternative is metadata nothing can settle, which sends a consumer
    back to a source it was never given.

    There is no reader to borrow for this one -- mypy parses straight
    into its own shape and has nothing that puts it back -- but JSON is
    not a format that needs one.
    """
    try:
        meta = json.loads(data)
        source = meta.get("path")
        resolved = len(meta["dependencies"])
        unresolved = len(meta["suppressed"])
        # The second metadata file carries neither list, so absence is
        # fine and only a length that cannot be accounted for is not.
        per_import = {key: meta[key] for key in _PER_IMPORT if key in meta}
    except (AttributeError, KeyError, TypeError, ValueError):
        return data, None

    path = source if isinstance(source, str) else None
    if not unresolved or any(
        len(value) != resolved + unresolved for value in per_import.values()
    ):
        return data, path

    meta["suppressed"] = []
    for key, value in per_import.items():
        meta[key] = value[:resolved]
    if "suppressed_deps_opts" in meta:
        # The digest of the unresolved imports, written as hex, and
        # written as nothing at all when there are none left to digest.
        meta["suppressed_deps_opts"] = ""

    return json.dumps(meta, sort_keys=True, separators=(",", ":")).encode("utf-8"), path
