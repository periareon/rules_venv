"""Library first party package

All `library` imports are expected to be first part
due to the `imports = ["."]` specified on the Bazel
target.
"""

import tomlkit

import library.first_party_2  # type: ignore
from library.first_party_3 import goodbye  # type: ignore


def conversation() -> None:
    """Print a conversation."""
    library.first_party_2.greeting()
    print(tomlkit.__name__)
    goodbye()
