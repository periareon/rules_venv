"""Tests confirming pylint is able to handle imports."""

import fibonacci  # type: ignore
import python.pylint.private.tests.imports

del fibonacci
print(python.pylint.private.tests.imports)
