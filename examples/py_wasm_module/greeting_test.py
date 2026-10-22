"""Checks the answer the consumer's repository rule got from the module."""

import os
import platform
import unittest

from python.runfiles import Runfiles


class GreetingTest(unittest.TestCase):
    """The module ran under `execute_wasm` and answered."""

    def test_greeting(self) -> None:
        """The answer names the caller and the embedded Python."""
        runfiles = Runfiles.Create()
        assert runfiles
        # TODO: https://github.com/periareon/rules_venv/issues/37
        source_repo = "" if platform.system() == "Windows" else None
        path = runfiles.Rlocation(os.environ["GREETING"], source_repo)
        assert path
        with open(path, encoding="utf-8") as handle:
            greeting = handle.read()
        self.assertTrue(greeting.startswith("Hello, rules_venv! From Python 3.14"), greeting)
        self.assertIn("on wasi", greeting)


if __name__ == "__main__":
    unittest.main()
