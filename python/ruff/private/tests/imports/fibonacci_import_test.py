"""Tests confirming ruff is able to handle imports."""

import fibonacci  # type: ignore
import python.ruff.private.tests.imports

del fibonacci
print(python.ruff.private.tests.imports)
