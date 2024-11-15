"""Unit tests"""

import os
import unittest


class TestTemplateVariableInfo(unittest.TestCase):
    """Tests confirming interactions TemplateVariableInfo works."""

    def test_expanded_var(self) -> None:
        """Test variable expansions in env vars."""
        self.assertEqual(os.environ["EXPANDED_VAR"], "Hello World!")


if __name__ == "__main__":
    unittest.main()
