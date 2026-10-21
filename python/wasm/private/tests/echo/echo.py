"""The entry module of the `py_wasm_module` smoke test."""

import json
import sys


def echo(payload: bytes) -> bytes:
    """Return the input unchanged."""
    return payload


def info(payload: bytes) -> tuple[bytes, int]:
    """Describe the interpreter, as JSON, and set a return code from the input."""
    code = int(payload or b"0")
    report = {
        "version": sys.version,
        "platform": sys.platform,
        "modules": sorted(name for name in sys.modules if name.startswith("json")),
    }
    return json.dumps(report).encode("utf-8"), code


def raises(payload: bytes) -> bytes:
    """Fail, to show what a raised exception comes back as."""
    raise ValueError(f"as requested: {payload!r}")
