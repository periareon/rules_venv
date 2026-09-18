"""Tests confirming pylint is able to handle imports."""

import fibonacci
import python.pylint.private.tests.imports

del fibonacci
print(python.pylint.private.tests.imports)
