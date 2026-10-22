"""Checks of the `py_wasm_module` smoke test's output.

The module itself is inspected: it must import nothing, export `allocate` and
the functions of `echo.py`, and have a single memory, as the documented calling
convention promises. When the `wasmtime` package is importable the module is
also called through that convention.
"""

import json
import os
import platform
import unittest

from python.runfiles import Runfiles

try:
    # Only the development environment has a runtime; the module checks run anywhere.
    import wasmtime  # type: ignore[import-not-found,unused-ignore] # pylint: disable=import-error
except ImportError:
    wasmtime = None

IMPORT_SECTION = 2
MEMORY_SECTION = 5
EXPORT_SECTION = 7


def _leb(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return result, pos


def _sections(data: bytes) -> dict[int, bytes]:
    if data[:8] != b"\0asm\x01\0\0\0":
        raise AssertionError("not a WebAssembly module")
    sections = {}
    pos = 8
    while pos < len(data):
        section_id = data[pos]
        size, body_start = _leb(data, pos + 1)
        if section_id != 0:
            sections[section_id] = data[body_start : body_start + size]
        pos = body_start + size
    return sections


def _export_names(body: bytes) -> list[str]:
    count, pos = _leb(body, 0)
    names = []
    for _ in range(count):
        length, pos = _leb(body, pos)
        names.append(body[pos : pos + length].decode("utf-8"))
        pos += length
        pos += 1  # kind
        _, pos = _leb(body, pos)  # index
    return names


def _module_path() -> str:
    runfiles = Runfiles.Create()
    assert runfiles
    # TODO: https://github.com/periareon/rules_venv/issues/37
    source_repo = "" if platform.system() == "Windows" else None
    path = runfiles.Rlocation(os.environ["ECHO_WASM"], source_repo)
    assert path
    return path


class ModuleTest(unittest.TestCase):
    """The module has the documented shape."""

    def setUp(self) -> None:
        """Parse the module's sections."""
        with open(_module_path(), "rb") as handle:
            self.sections = _sections(handle.read())

    def test_no_imports(self) -> None:
        """The import section is absent or empty."""
        body = self.sections.get(IMPORT_SECTION)
        if body is not None:
            count, _ = _leb(body, 0)
            self.assertEqual(count, 0)

    def test_exports(self) -> None:
        """`allocate`, the memory and every export of `echo.py` are exported."""
        names = _export_names(self.sections[EXPORT_SECTION])
        for name in ("allocate", "echo", "info", "raises", "memory"):
            self.assertIn(name, names)
        # Pre-initialization ran `wizer.initialize` already and must not be rerun.
        self.assertNotIn("wizer.initialize", names)

    def test_single_memory(self) -> None:
        """One memory, as the calling convention assumes."""
        count, _ = _leb(self.sections[MEMORY_SECTION], 0)
        self.assertEqual(count, 1)


def _execute(path: str, function: str, data: bytes) -> tuple[int, bytes]:
    """Call the module through the documented calling convention."""
    store = wasmtime.Store(wasmtime.Engine())
    module = wasmtime.Module.from_file(store.engine, path)
    exports = wasmtime.Instance(store, module, []).exports(store)
    memory = exports["memory"]

    input_ptr = exports["allocate"](store, len(data), 1)
    memory.write(store, data, input_ptr)
    # struct { output_ptr_ptr: **u8, output_len_ptr: *u32 }
    params = exports["allocate"](store, 8, 4)
    memory.write(store, b"\0" * 8, params)
    code = exports[function](store, input_ptr, len(data), params, params + 4)
    out_ptr = int.from_bytes(memory.read(store, params, params + 4), "little")
    out_len = int.from_bytes(memory.read(store, params + 4, params + 8), "little")
    return code, bytes(memory.read(store, out_ptr, out_ptr + out_len))


class CallTest(unittest.TestCase):
    """The exports behave as documented, when a runtime is available."""

    def setUp(self) -> None:
        """Skip without a runtime to run the module with."""
        if wasmtime is None:
            self.skipTest("the wasmtime package is not available")
        self.path = _module_path()

    def test_echo(self) -> None:
        """Bytes come back unchanged, non-ASCII included."""
        code, output = _execute(self.path, "echo", "héllo".encode())
        self.assertEqual((code, output), (0, "héllo".encode()))

    def test_info_sets_code(self) -> None:
        """A `(bytes, code)` return sets the return code."""
        code, output = _execute(self.path, "info", b"7")
        self.assertEqual(code, 7)
        report = json.loads(output)
        self.assertEqual(report["platform"], "wasi")
        self.assertTrue(report["version"].startswith(os.environ["ECHO_PYTHON_VERSION"]))

    def test_exception(self) -> None:
        """An exception is return code 2 with the traceback in the output."""
        code, output = _execute(self.path, "raises", b"x")
        self.assertEqual(code, 2)
        self.assertIn(b"ValueError: as requested", output)


if __name__ == "__main__":
    unittest.main()
