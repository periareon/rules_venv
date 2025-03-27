"""Demonstrate mixing first party modules from another package

We should see `library` imports shown as first party even though there's no
`__init__.py` file defined in `python.isort.private.tests.imports.deps.library`.
It's still considered the namespace of first party package and thus should support
imports as first party
"""

import os

import tomlkit

import python.isort.private.tests.namespaces.library.first_party_1
from python.isort.private.tests.namespaces.library import first_party_2, first_party_3


def example_1() -> None:
    """Call some code"""
    print(os.curdir)

    first_party_2.greeting()

    print(tomlkit.__name__)

    first_party_3.goodbye()


def example_2() -> None:
    """Call some other code"""
    python.isort.private.tests.namespaces.library.first_party_1.conversation()
