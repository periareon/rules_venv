"""The entry module of the example: one function per export of the module."""

import sys


def greet(payload: bytes) -> bytes:
    """Greet whoever the input names, and say which Python did."""
    name = payload.decode("utf-8") or "world"
    version = sys.version.split()[0]
    return f"Hello, {name}! From Python {version} on {sys.platform}.\n".encode("utf-8")
