# Runs inside the embedded interpreter before anything else is imported.
#
# Installs an importer over the bundle linked into the module, so that the
# unmodified Python sources of the module's dependencies import without a
# filesystem, then imports the entry module the exports call into.
import _frozen_importlib as _bootstrap
import sys

import _host

_MAGIC = b"RVB1"
_ROOT = "/bundle/"


def _read_bundle(data):
    """Index the bundle: `RVB1`, then (u32 name length, name, u32 size, bytes)*."""
    if bytes(data[:4]) != _MAGIC:
        raise RuntimeError("bad bundle magic")
    files = {}
    offset = 4
    end = len(data)
    while offset < end:
        name_len = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        name = bytes(data[offset : offset + name_len]).decode("utf-8")
        offset += name_len
        size = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        files[name] = (offset, size)
        offset += size
    return files


class BundleFinder:
    """Import modules, packages and namespace packages from the bundle."""

    def __init__(self, data):
        self._data = data
        self._files = _read_bundle(data)
        # Every directory holding an entry, for namespace packages.
        self._dirs = set()
        for name in self._files:
            parts = name.split("/")[:-1]
            for index in range(1, len(parts) + 1):
                self._dirs.add("/".join(parts[:index]))

    def find_spec(self, name, path=None, target=None):
        base = name.replace(".", "/")
        for stem, is_package in ((base + "/__init__", True), (base, False)):
            for extension in (".pyc", ".py"):
                candidate = stem + extension
                if candidate in self._files:
                    spec = _bootstrap.ModuleSpec(
                        name, self, origin=_ROOT + candidate, is_package=is_package
                    )
                    spec.has_location = True
                    if is_package:
                        spec.submodule_search_locations = [_ROOT + base]
                    return spec
        if base in self._dirs:
            # A directory without `__init__`: a namespace package.
            spec = _bootstrap.ModuleSpec(name, None, is_package=True)
            spec.submodule_search_locations = [_ROOT + base]
            return spec
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        origin = module.__spec__.origin
        offset, size = self._files[origin[len(_ROOT) :]]
        data = bytes(self._data[offset : offset + size])
        if origin.endswith(".pyc"):
            # Bytecode marshalled by `bundle.py --pyc` with a matching interpreter.
            import marshal

            module.__file__ = origin[: -len(".pyc")] + ".py"
            code = marshal.loads(data)
        else:
            module.__file__ = origin
            code = compile(data, origin, "exec", dont_inherit=True)
        exec(code, module.__dict__)

    def get_source(self, name):
        spec = self.find_spec(name)
        if spec is None or spec.origin is None or spec.origin.endswith(".pyc"):
            return None
        offset, size = self._files[spec.origin[len(_ROOT) :]]
        return bytes(self._data[offset : offset + size]).decode("utf-8")


# Put the bundle first; from here on every import is served from it.
sys.meta_path.insert(0, BundleFinder(_host.bundle()))


def prepare(name):
    """Import the entry module once the interpreter is fully initialized.

    With Wizer this runs at build time, so a call finds the module imported
    already.
    """
    import importlib

    return importlib.import_module(name)
