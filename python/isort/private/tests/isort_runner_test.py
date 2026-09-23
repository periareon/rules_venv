"""Tests for the config generation in `isort_runner`."""

import configparser
import os
import tempfile
import tomllib
import unittest
from pathlib import Path

from isort.settings import Config

from python.isort.private import isort_runner

SRC_PATHS = ["/venv/first_party", "/venv/second_party"]

PYPROJECT_TOML = """\
[build-system]
requires = ["setuptools"]

[tool.isort]
profile = "black"
line_length = 88
src_paths = ["existing"]
known_first_party = ["pkg"]

[tool.other]
unrelated = true
"""


class GenerateConfigTest(unittest.TestCase):
    """Test cases for `isort_runner.generate_config_with_projects`."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(dir=os.environ.get("TEST_TMPDIR", None)))
        return super().setUp()

    def _generate(self, name: str, content: str) -> Path:
        """Write a config, run it through the generator, return the copy."""
        existing = self.temp_dir / "src" / name
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text(content, encoding="utf-8")

        output = self.temp_dir / "out" / name
        output.parent.mkdir(parents=True, exist_ok=True)
        isort_runner.generate_config_with_projects(
            existing=existing, output=output, src_paths=list(SRC_PATHS)
        )
        return output

    def test_isort_cfg(self) -> None:
        """A `.isort.cfg` keeps its settings under `[settings]`."""
        output = self._generate(
            ".isort.cfg", "[settings]\nprofile = black\nsrc_paths = existing\n"
        )

        config = configparser.ConfigParser()
        config.read(str(output))
        self.assertEqual(config.get("settings", "profile"), "black")
        self.assertEqual(
            config.get("settings", "src_paths"),
            ",".join(sorted(SRC_PATHS + ["existing"])),
        )

    def test_setup_cfg(self) -> None:
        """A `setup.cfg` keeps its settings under `[isort]`."""
        output = self._generate("setup.cfg", "[isort]\nprofile = black\n")

        config = configparser.ConfigParser()
        config.read(str(output))
        self.assertEqual(config.get("isort", "profile"), "black")
        self.assertEqual(config.get("isort", "src_paths"), ",".join(sorted(SRC_PATHS)))

    def test_pyproject_toml(self) -> None:
        """A `pyproject.toml` keeps only its `tool.isort` table."""
        output = self._generate("pyproject.toml", PYPROJECT_TOML)

        with output.open("rb") as fhd:
            written = tomllib.load(fhd)

        settings = written["tool"]["isort"]
        self.assertEqual(settings["profile"], "black")
        self.assertEqual(settings["line_length"], 88)
        self.assertEqual(settings["known_first_party"], ["pkg"])
        self.assertEqual(settings["src_paths"], sorted(SRC_PATHS + ["existing"]))
        self.assertNotIn("other", written["tool"])
        self.assertNotIn("build-system", written)

    def test_pyproject_toml_without_isort_settings(self) -> None:
        """A `pyproject.toml` that says nothing about isort still works."""
        output = self._generate("pyproject.toml", "[tool.other]\nunrelated = true\n")

        with output.open("rb") as fhd:
            written = tomllib.load(fhd)

        self.assertEqual(written["tool"]["isort"]["src_paths"], sorted(SRC_PATHS))

    def test_toml_settings_reach_isort(self) -> None:
        """isort reads the generated file back as the settings written."""
        output = self._generate(
            "pyproject.toml",
            '[tool.isort]\nprofile = "black"\nknown_first_party = ["pkg"]\n',
        )

        config = Config(settings_file=str(output))
        self.assertEqual(config.profile, "black")
        self.assertIn("pkg", config.known_first_party)
        root = output.parent
        for path in SRC_PATHS:
            self.assertIn(root / path, config.src_paths)

    def test_unknown_config(self) -> None:
        """A file isort cannot read is refused rather than guessed at."""
        with self.assertRaises(ValueError):
            self._generate("isort.conf", "[isort]\n")


if __name__ == "__main__":
    unittest.main()
