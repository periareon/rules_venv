"""Checks the answer the consumer's repository rule got from the module."""

import os
import unittest

from python.runfiles import Runfiles


class GreetingTest(unittest.TestCase):
    """The module ran under `execute_wasm` and answered."""

    def test_greeting(self) -> None:
        """The answer names the caller and the embedded Python."""
        runfiles = Runfiles.Create()
        assert runfiles
        path = runfiles.Rlocation(os.environ["GREETING"])
        assert path
        with open(path, encoding="utf-8") as handle:
            greeting = handle.read()
        self.assertTrue(greeting.startswith("Hello, rules_venv! From Python 3.14"), greeting)
        self.assertIn("on wasi", greeting)


if __name__ == "__main__":
    unittest.main()
