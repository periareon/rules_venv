"""Pack Python sources into the bundle `bootstrap.py` imports from.

A bundle is a flat archive: the magic ``RVB1`` followed by entries of
``(u32 name length, name, u32 size, bytes)``. Names are import paths with
``/`` separators, ending in ``.py`` for sources or ``.pyc`` for bytecode
marshalled by an interpreter of the version that will load them.

Usage:
    bundle.py --out OUT [--stdlib LIBDIR] [--file NAME=PATH]...
              [--pyc [--expect-version X.Y]]
"""

import argparse
import marshal
import os
import struct
import sys
from collections.abc import Iterator
from pathlib import Path

MAGIC = b"RVB1"

# Parts of a CPython `Lib` directory an embedded interpreter never needs.
STDLIB_SKIP = {
    "__phello__",
    "__pycache__",
    "ctypes",
    "ensurepip",
    "idlelib",
    "lib-dynload",
    "lib2to3",
    "pydoc_data",
    "site-packages",
    "test",
    "tkinter",
    "turtledemo",
    "venv",
}


def collect(root: Path, skip: set[str]) -> Iterator[tuple[str, Path]]:
    """Yield ``(bundle name, path)`` for every ``.py`` file under ``root``."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in skip
            and not d.endswith(".dist-info")
            and not d.startswith("config-")
        )
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = Path(dirpath) / filename
            yield path.relative_to(root).as_posix(), path


def parse_args() -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__, fromfile_prefix_chars="@")
    parser.add_argument("--out", type=Path, required=True, help="The bundle to write.")
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="A single file as `NAME=PATH`, where NAME is its bundle name.",
    )
    parser.add_argument(
        "--stdlib",
        type=Path,
        help="A CPython `Lib` directory, trimmed of what is never needed.",
    )
    parser.add_argument(
        "--pyc",
        action="store_true",
        help=(
            "Store marshalled bytecode instead of source. The running interpreter "
            "must be the version embedded in the module."
        ),
    )
    parser.add_argument(
        "--expect-version",
        help="With `--pyc`, the `X.Y` the bytecode is for; fails when this interpreter differs.",
    )
    return parser.parse_args()


def gather(args: argparse.Namespace) -> dict[str, Path]:
    """The files the arguments name, by bundle name; a `--file` overrides the standard library."""
    entries: dict[str, Path] = {}
    if args.stdlib:
        entries.update(collect(args.stdlib, STDLIB_SKIP))
    for spec in args.file:
        name, _, path = spec.partition("=")
        if not path:
            raise SystemExit(f"--file expects NAME=PATH, got {spec!r}")
        entries[name.replace(os.sep, "/")] = Path(path)
    return entries


def compile_source(name: str, data: bytes) -> tuple[str, bytes] | None:
    """Marshal a source file's code, or None for a file that does not compile."""
    try:
        code = compile(data, "/bundle/" + name, "exec", dont_inherit=True)
    except SyntaxError:
        # Some stdlib files are templates or deliberately invalid.
        return None
    return name[: -len(".py")] + ".pyc", marshal.dumps(code)


def write_bundle(out: Path, entries: dict[str, Path], pyc: bool) -> tuple[int, int]:
    """Write the bundle; returns the number of entries and their total size."""
    total = 0
    count = 0
    with open(out, "wb") as handle:
        handle.write(MAGIC)
        for name in sorted(entries):
            data = entries[name].read_bytes()
            if pyc and name.endswith(".py"):
                compiled = compile_source(name, data)
                if compiled is None:
                    continue
                name, data = compiled
            encoded = name.encode("utf-8")
            handle.write(struct.pack("<I", len(encoded)))
            handle.write(encoded)
            handle.write(struct.pack("<I", len(data)))
            handle.write(data)
            total += len(data)
            count += 1
    return count, total


def main() -> None:
    """The main entrypoint."""
    args = parse_args()
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if args.pyc and args.expect_version and args.expect_version != version:
        raise SystemExit(
            f"bundle.py runs under Python {version} but the module embeds Python "
            f"{args.expect_version}; their bytecode differs."
        )
    count, total = write_bundle(args.out, gather(args), args.pyc)
    kind = (
        f"bytecode for Python {sys.version_info.major}.{sys.version_info.minor}"
        if args.pyc
        else "source"
    )
    print(f"bundled {count} files, {total} bytes ({kind})")


if __name__ == "__main__":
    main()
