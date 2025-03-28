"""Demonstrate mixing first party modules from another package

We expect `library` imports to show as third party due to the use of the
`imports` attribute on the `//python/isort/private/imports/deps:library`
target. However, using repo absolute import paths will still be considered
first party even though other paths are third party.
"""

import os

import library.first_party_2  # type: ignore

import python.isort.private.tests.imports.deps.library.first_party_3


def example() -> None:
    """Example code."""
    print(os.curdir)

    library.first_party_2.greeting()

    python.isort.private.tests.imports.deps.library.first_party_3.goodbye()
