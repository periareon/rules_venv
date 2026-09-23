"""Tests for the config generation in `mypy_options`."""

import configparser
import os
import tempfile
import tomllib
import unittest
from pathlib import Path

from mypy.config_parser import parse_config_file
from mypy.options import Options

from python.mypy.private import mypy_options

SEARCH_PATHS = ["first", "second"]

PYPROJECT_TOML = """\
[build-system]
requires = ["setuptools"]

[tool.mypy]
strict = true
python_version = "3.11"
files = ["src"]

[[tool.mypy.overrides]]
module = ["third_party.*"]
ignore_errors = true

[tool.other]
unrelated = true
"""


class GenerateConfigTest(unittest.TestCase):
    """Test cases for `mypy_options.generate_config`."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(dir=os.environ.get("TEST_TMPDIR", None)))
        self.out_dir = self.temp_dir / "out"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        return super().setUp()

    def _generate(self, name: str, content: str, *, silence_imports: bool) -> Path:
        """Write a config, run it through the generator, return the copy."""
        existing = self.temp_dir / "src" / name
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text(content, encoding="utf-8")

        return mypy_options.generate_config(
            original_config=existing,
            search_paths=SEARCH_PATHS,
            tmp_dir=self.out_dir,
            silence_imports=silence_imports,
        )

    def _options(self, config: Path) -> Options:
        """Read a generated config the way mypy itself would."""
        options = Options()
        parse_config_file(options, lambda: None, str(config), None, None)
        return options

    def test_ini(self) -> None:
        """An INI config keeps its settings and gains the silencing ones."""
        generated = self._generate(
            "mypy.ini",
            "[mypy]\nstrict = True\n\n[mypy-third_party.*]\nignore_errors = True\n",
            silence_imports=True,
        )
        self.assertEqual(generated.name, "mypy.ini")

        config = configparser.ConfigParser()
        config.read(str(generated))
        self.assertEqual(config.get("mypy", "strict"), "True")
        self.assertEqual(config.get("mypy", "follow_imports"), "silent")
        self.assertEqual(config.get("mypy", "follow_imports_for_stubs"), "True")
        self.assertTrue(config.has_section("mypy-third_party.*"))

    def test_toml(self) -> None:
        """A TOML config keeps only `tool.mypy`, with its types intact."""
        generated = self._generate(
            "pyproject.toml", PYPROJECT_TOML, silence_imports=True
        )
        self.assertEqual(generated.suffix, ".toml")

        with generated.open("rb") as fhd:
            written = tomllib.load(fhd)

        settings = written["tool"]["mypy"]
        self.assertIs(settings["strict"], True)
        self.assertEqual(settings["python_version"], "3.11")
        self.assertEqual(settings["files"], ["src"])
        self.assertEqual(settings["follow_imports"], "silent")
        self.assertIs(settings["follow_imports_for_stubs"], True)
        self.assertEqual(
            settings["overrides"],
            [{"module": ["third_party.*"], "ignore_errors": True}],
        )
        self.assertNotIn("other", written["tool"])
        self.assertNotIn("build-system", written)

    def test_toml_is_read_back_as_the_same_options(self) -> None:
        """mypy reads the generated TOML as the settings that went in."""
        generated = self._generate(
            "pyproject.toml",
            '[tool.mypy]\nstrict = true\npython_version = "3.11"\n',
            silence_imports=True,
        )

        options = self._options(generated)
        self.assertEqual(options.follow_imports, "silent")
        self.assertTrue(options.follow_imports_for_stubs)
        self.assertEqual(options.python_version, (3, 11))

    def test_ini_and_toml_agree(self) -> None:
        """The two formats are two spellings of one set of options.

        A cache is keyed on the options that produced it, so a workspace
        that writes its settings in TOML has to reach the same options
        an INI spelling of them would -- otherwise moving a config from
        one to the other would quietly throw the build's caches away.
        """
        ini = self._options(
            self._generate(
                "mypy.ini",
                "[mypy]\nstrict = True\npython_version = 3.11\n",
                silence_imports=True,
            )
        )
        toml = self._options(
            self._generate(
                "pyproject.toml",
                '[tool.mypy]\nstrict = true\npython_version = "3.11"\n',
                silence_imports=True,
            )
        )

        # Every option, less the one that cannot agree: mypy records
        # which file it read, and the two are two files. The options a
        # cache is keyed on are a subset of these, so comparing all of
        # them says what the docstring asks and more.
        ini_snapshot = ini.snapshot()
        toml_snapshot = toml.snapshot()
        self.assertEqual(
            ini_snapshot.pop("config_file"), str(self.out_dir / "mypy.ini")
        )
        self.assertEqual(
            toml_snapshot.pop("config_file"), str(self.out_dir / "mypy.toml")
        )
        self.assertEqual(ini_snapshot, toml_snapshot)

    def test_without_silencing(self) -> None:
        """An uncached run adds nothing of its own to the config."""
        generated = self._generate(
            "pyproject.toml", "[tool.mypy]\nstrict = true\n", silence_imports=False
        )

        with generated.open("rb") as fhd:
            settings = tomllib.load(fhd)["tool"]["mypy"]

        self.assertEqual(settings, {"strict": True})

    def test_toml_without_mypy_settings(self) -> None:
        """A TOML config that says nothing about mypy is still readable."""
        generated = self._generate(
            "pyproject.toml", "[tool.other]\nunrelated = true\n", silence_imports=False
        )

        with generated.open("rb") as fhd:
            self.assertEqual(tomllib.load(fhd), {"tool": {"mypy": {}}})

    def test_environment(self) -> None:
        """The search paths and the config's own directory are published."""
        existing_dir = self.temp_dir / "src"
        self._generate("mypy.ini", "[mypy]\n", silence_imports=False)

        self.assertEqual(os.environ["MYPYPATH"], os.pathsep.join(SEARCH_PATHS))
        self.assertEqual(os.environ["MYPY_CONFIG_FILE_DIR"], str(existing_dir))


if __name__ == "__main__":
    unittest.main()
