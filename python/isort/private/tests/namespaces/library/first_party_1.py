"""Library first party package

All `library` imports are expected to be first part
due to the `imports = ["."]` specified on the Bazel
target.
"""

import tomlkit

import python.isort.private.tests.namespaces.library.first_party_2
from python.isort.private.tests.namespaces.library.first_party_3 import goodbye


def conversation() -> None:
    """Print a conversation."""
    python.isort.private.tests.namespaces.library.first_party_2.greeting()
    print(tomlkit.__name__)
    goodbye()
