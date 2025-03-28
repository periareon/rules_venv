"""Wrapper to run pytest and gather coverage into an LCOV database."""

import argparse
import configparser
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import NamedTuple, Optional, Sequence

import coverage
from coverage.cmdline import main as coverage_main
from python.runfiles import Runfiles


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runifle.
    """
    source_repo = os.environ["TEST_WORKSPACE"]
    runfile = runfiles.Rlocation(rlocationpath, source_repo)
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def parse_args(
    runfiles: Runfiles, args: Optional[Sequence[str]] = None
) -> argparse.Namespace:
    """Parse command line arguments

    Args:
        runfiles: A runfiles object for looking up files.
        args: Arguments to use over `sys.argv`
    """

    def _rlocationpath(value: str) -> Path:
        return _rlocation(runfiles, value)

    parser = argparse.ArgumentParser(prog="pytest_process_wrapper", usage=__doc__)
    parser.add_argument(
        "--cov-config",
        required=True,
        type=_rlocationpath,
        help="Path to a `coverage.py` rc file (e.g. `coveragerc`).",
    )
    parser.add_argument(
        "--pytest-config",
        required=True,
        type=_rlocationpath,
        help="Path to a pytest config file (e.g. `pyproject.toml`).",
    )
    parser.add_argument(
        "--src",
        dest="sources",
        type=_rlocationpath,
        action="append",
        default=[],
        required=True,
        help="Source files to test",
    )
    parser.add_argument(
        "-n",
        "--numprocesses",
        dest="numprocesses",
        type=int,
        default=None,
        help="The `-n numprocesses` value for `pytest-xdist`.",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional arguments to pass to pytest.",
    )

    if args is not None:
        parsed_args = parser.parse_args(args)
    else:
        parsed_args = parser.parse_args()

    # Ensure that the given ytest args
    pytest_parser = argparse.ArgumentParser("internal_parser")
    pytest_parser.add_argument(
        "-n",
        "--numprocesses",
        dest="numprocesses",
        type=int,
        help="Illegal pytest-xdist argument.",
    )
    pytest_args, remaining = pytest_parser.parse_known_args(parsed_args.pytest_args)

    # Strip out the `numprocesses` argument.
    parsed_args.pytest_args = remaining

    if pytest_args.numprocesses:
        if parsed_args.numprocesses != pytest_args.numprocesses:
            parser.error(
                "`--numprocesses` (`-n`) must be an argument to the process runner. "
                "Please update the Bazel target to use the `numprocesses` attribute."
            )

    return parsed_args


class PytestCapabilities(NamedTuple):
    """Capabilities available via detected pytest plugins"""

    coverage: bool
    """`pytest-cov` is available."""

    xdist: bool
    """`pytest-xdist` is available."""

    shard: bool
    """`pytest-shard` is available."""


def query_pytest_capabilities() -> PytestCapabilities:
    """Query the current pytest environment for it's capabilities."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--help"],
            encoding="utf-8",
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise EnvironmentError("Failed to query pytest capabilities") from exc

    supports_coverage = False
    supports_xdist = False
    supports_shard = False
    for line in result.stdout.splitlines():
        text = line.strip()
        if text.startswith(("--cov=[SOURCE]", "--no-cov")):
            supports_coverage = True
            continue

        if text.startswith(("-n numprocesses", "--dist=distmode")):
            supports_xdist = True
            continue

        if text.startswith(("--shard-id=SHARD_ID", "--num-shards=NUM_SHARDS")):
            supports_shard = True
            continue

    return PytestCapabilities(
        coverage=supports_coverage, xdist=supports_xdist, shard=supports_shard
    )


CoverageSourceMap = dict[Path, PurePosixPath]
"""A mapping of `execpath` to `rootpath` for files to collect coverage for.

For more details, see documentation on Bazel make variables:
https://docs.bazel.build/versions/main/be/make-variables.html#predefined_label_variables
"""


def collect_coverage_sources(runfiles: Runfiles, manifest: Path) -> CoverageSourceMap:
    """Generate a map of files to collect coverage for.

    Args:
        runfiles: A runfiles object for looking up files.
        manifest: A manifest containing newline delimited source paths.

    Returns:
        A map of absolute paths to relative paths for coverage sources.
    """
    workspace = PurePosixPath(os.environ["TEST_WORKSPACE"])

    sources = {}
    for line in manifest.read_text().splitlines():
        text = line.strip()
        # The coverage manifest may include files such as `.gcno` from other instrumented
        # runfiles, for python these other coverage outputs are ignored.
        if text.startswith("bazel-out"):
            continue

        rlocationpath = (workspace / line).as_posix()
        src = _rlocation(runfiles, rlocationpath)
        sources.update({Path(src): PurePosixPath(line)})

    return sources


def splice_coverage_config(
    cov_config_path: Path, coverage_sources: CoverageSourceMap, data_file: Path
) -> Path:
    """Modify a `coveragerc` file to explicitly include or omit source files from Bazel's coverage manifest.

    Args:
        cov_config_path: The path to an existing `coveragerc` file.
        coverage_sources: Source files to run coverage on.
        data_file: The path where coverage data should be written.

    Returns:
        The path to the updated coverage config file.
    """
    # Write the new includes to an rc file
    cov_config = configparser.ConfigParser()
    cov_config.read(str(cov_config_path))

    # Ensure the `run` section exists
    if "run" not in cov_config.sections():
        cov_config.add_section("run")

    # Force the data file to be an expected path
    cov_config.set("run", "data_file", str(data_file))

    # Grab any existing coverage.py include or omit settings
    includes = cov_config.get("run", "include", fallback="")
    omits = cov_config.get("run", "omit", fallback="")

    # In cases where a coverage manifest is provided but it's empty, we interpret
    # that to be a test that has no dependencies from the same workspace and
    # by extension, no dependencies used for coverage. All sources are then
    # excluded from collecting coverage. Users who do not expect coverage to be
    # collected from `deps` targets should annotate their `.coveragerc` file to
    # collect the correct inputs from the `data` attribute.
    if coverage_sources:
        if includes:
            existing_includes = includes.split(",")
        else:
            existing_includes = []
        existing_includes.extend([str(src) for src in sorted(coverage_sources.keys())])
        cov_config.set("run", "include", "\n".join(existing_includes))

    elif not includes and not omits:
        cov_config.set("run", "omit", "*")

    updated_cov_config = Path(os.environ["TEST_TMPDIR"]) / ".coveragerc"
    with updated_cov_config.open("w", encoding="utf-8") as fhd:
        cov_config.write(fhd)

    return updated_cov_config


def load_args_file(runfiles: Runfiles) -> Optional[list[str]]:
    """Attempt to load a Bazel provided args file from the environment.

    Args:
        runfiles: A runfiles object for looking up files.

    Returns:
        A list of args if a args file was found.
    """
    argv = None
    if "RULES_VENV_PYTEST_TEST_ARGS_FILE" in os.environ:
        args_file = _rlocation(runfiles, os.environ["RULES_VENV_PYTEST_TEST_ARGS_FILE"])
        argv = args_file.read_text(encoding="utf-8").splitlines() + sys.argv[1:]
    return argv


def relativize_sf(line: bytes, coverage_sources: dict[Path, PurePosixPath]) -> bytes:
    """Parses a line of a lcov coverage file and normalizes source file (SF) paths

    Args:
        line: A line from a lcov coverage file
        coverage_sources: A mapping of real (`os.path.realpath`) file paths to
            relative paths to the same source file from the Bazel exec root.

    Returns:
        bytes: The sanitized lcov line.
    """
    # Skip lines that aren't representing source files
    if not line.startswith(b"SF:"):
        return line
    # Check if the source file has a map to a relative path
    source = Path(line[3:].decode("utf-8"))
    if source in coverage_sources:
        return b"SF:" + str(coverage_sources[source]).encode()

    return line


def abs_file(filename: str) -> str:
    """Return the absolute normalized form of `filename`."""
    return os.path.abspath(filename)


def normalize_path(filename: str) -> str:
    """Normalize a file/dir name for comparison purposes."""
    return os.path.normcase(os.path.normpath(filename))


def patch_realpaths() -> None:
    """Patch os.path.realpath escapes. Coverage will be loaded even if not being
    collected, so to be safe patch no matter what.
    """
    coverage.files.abs_file = abs_file  # type: ignore
    coverage.control.abs_file = abs_file  # type: ignore
    coverage.files.set_relative_directory()


def dump_coverage(
    coverage_file: Path,
    coverage_config: Optional[Path],
    coverage_sources: CoverageSourceMap,
    coverage_output_file: Path,
) -> None:
    """Dump coverage to LCOV format and verify coverage minimums are met.

    Args:
        coverage_file: Output coverage file to write.
        coverage_config: The path to a coveragerc file
        coverage_sources: A map of paths to files within the sandbox to collect coverage for
        coverage_output_file: The location where the lcov coverage file should be written.
    """

    cov_args = [
        "--data-file",
        str(coverage_file),
    ]

    if coverage_config:
        cov_args.extend(["--rcfile", str(coverage_config)])

    # Convert to LCOV and place where Bazel requests.
    coverage_main(["lcov", "-o", str(coverage_output_file)] + cov_args)

    # Resolve the sandboxed files to absolute paths on the host's file system
    real_path_cov_srcs = {src.resolve(): path for src, path in coverage_sources.items()}

    # Fixup the coverage file to ensure any absolute paths are corrected
    # to be relative paths from the root fo the sandbox
    if coverage_output_file.exists():
        cov_output_content = [
            relativize_sf(line, real_path_cov_srcs)
            for line in coverage_output_file.read_bytes().splitlines()
        ]
        coverage_output_file.write_bytes(b"\n".join(cov_output_content))


# pylint: disable-next=too-many-branches,too-many-statements,too-many-locals
def main() -> None:
    """Main execution."""
    patch_realpaths()

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles.")

    parsed_args = parse_args(runfiles, load_args_file(runfiles))

    capabilities = query_pytest_capabilities()

    temp_dir = Path(os.environ["TEST_TMPDIR"])
    home = temp_dir / "home"
    home.mkdir(exist_ok=True, parents=True)
    temp = temp_dir / "tmp"
    temp.mkdir(exist_ok=True, parents=True)

    child_env = dict(os.environ)
    child_env.update(
        {
            "HOME": str(home),
            "TEMP": str(temp),
            "TMP": str(temp),
            "TMPDIR": str(temp),
            "USERPROFILE": str(home),
        }
    )

    # Determine the directory in which pytest should run
    test_dir = Path.cwd()

    existing_python_path = os.getenv("PYTHONPATH", "")
    if existing_python_path:
        existing_python_path = os.pathsep + existing_python_path
    child_env["PYTHONPATH"] = str(test_dir) + existing_python_path

    # Custom arguments should not be passed to pytest here. This process wrapper
    # is only intended to have what's absolutely necessary to run pytest in a Bazel
    # test or coverage invocation. Custom arguments should be defined in the use of
    # rules which invoke this process wrapper or by providing `--pytest-config`.
    pytest_args = [
        sys.executable,
        "-m",
        "pytest",
    ]

    cov_config_path = parsed_args.cov_config
    coverage_sources = {}

    cov_enabled = os.getenv("COVERAGE") == "1"
    if cov_enabled:
        if not capabilities.coverage:
            raise EnvironmentError(
                "Bazel coverage was requested but `pytest-cov` plugin was not found."
            )

        coverage_file = Path(os.environ["TEST_TMPDIR"], ".coverage")
        child_env["COVERAGE_FILE"] = str(coverage_file)

        # Attempt to locate a coverage manifest indicating what files should be
        # included in coverage reports.
        if "COVERAGE_MANIFEST" in os.environ:
            coverage_manifest = Path(os.environ["COVERAGE_MANIFEST"])
            if "ROOT" in os.environ and not coverage_manifest.absolute():
                coverage_manifest = Path(os.environ["ROOT"]) / coverage_manifest

            coverage_sources = collect_coverage_sources(runfiles, coverage_manifest)

        # If no coverage sources are provided, then coverage is disabled.
        if not coverage_sources:
            pytest_args.append("--no-cov")
        else:
            cov_config_path = splice_coverage_config(
                cov_config_path=cov_config_path,
                coverage_sources=coverage_sources,
                data_file=coverage_file,
            )

            pytest_args.extend(
                [
                    "--cov",
                    "--cov-config",
                    str(cov_config_path),
                ]
            )

    else:
        if capabilities.coverage:
            pytest_args.append("--no-cov")

    # Emit JUnit XML if Bazel has specified an output file path.
    # https://bazel.build/reference/test-encyclopedia#initial-conditions
    xml_output_file = os.environ.get("XML_OUTPUT_FILE")
    if xml_output_file is not None:
        pytest_args.extend([f"--junitxml={xml_output_file}"])

    # Explicitly tell pytest where the root directory of the test is
    pytest_args.extend(["--rootdir", os.getcwd()])
    pytest_args.extend(["-c", str(parsed_args.pytest_config)])
    pytest_args.extend([str(src) for src in parsed_args.sources])

    # Append `pytest-xdist` args
    if parsed_args.numprocesses is not None:
        if not capabilities.xdist:
            raise EnvironmentError(
                "`numprocesses` was specified but `pytest-xdist` plugin was not found."
            )

        pytest_args.extend(["--numprocesses", str(parsed_args.numprocesses)])

    # Handle test sharding - requires pytest-shard plugin.
    if "TEST_SHARD_INDEX" in os.environ and "TEST_TOTAL_SHARDS" in os.environ:
        if not capabilities.shard:
            raise EnvironmentError("`pytest-shard` plugin was not found.")

        # Append `pytest-shard` args
        pytest_args.extend(
            [
                "--shard-id",
                os.environ["TEST_SHARD_INDEX"],
                "--num-shards",
                os.environ["TEST_TOTAL_SHARDS"],
            ]
        )

        # Touch the shard file to indicate support for sharding
        if "TEST_SHARD_STATUS_FILE" in os.environ:
            Path(os.environ["TEST_SHARD_STATUS_FILE"]).write_bytes(b"")

    # Append user args
    pytest_args.extend(parsed_args.pytest_args)

    try:
        result = subprocess.run(pytest_args, cwd=test_dir, env=child_env, check=False)
        # Exit code 5 indicates no tests were selected.
        if result.returncode not in (0, 5):
            sys.exit(result.returncode)
    finally:
        if cov_enabled:
            dump_coverage(
                coverage_file=coverage_file,
                coverage_config=cov_config_path,
                coverage_sources=coverage_sources,
                coverage_output_file=Path(
                    os.environ["COVERAGE_DIR"], "python_coverage.dat"
                ),
            )


if __name__ == "__main__":
    main()
