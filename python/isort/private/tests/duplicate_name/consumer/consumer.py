"""Show that imports which share a name with a workspace root package are sorted as third party.

The `python` package is first party depending on what is imported but in the case of `print_greeting`,
this package name is constructed using the `imports` attribute and packages discovered this way
are always considered third party.
"""

import pathlib

from python.within_second_python.py_dep import print_greeting
from tomlkit import __name__ as toml_name


def print_data() -> None:
    """Print some data"""
    print_greeting("Guten Tag!")
    print(pathlib.Path.cwd())
    print(toml_name)
