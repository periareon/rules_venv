"""A script for running ty within Bazel."""

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Optional, Sequence

from python.runfiles import Runfiles


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runfile.
    """
    runfile = runfiles.Rlocation(rlocationpath, source_repo=os.getenv("TEST_WORKSPACE"))
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def _maybe_runfile(arg: str) -> Path:
    """Parse an argument into a path while resolving runfiles.

    Not all contexts this script runs in will use runfiles. In
    these cases the function is a noop.
    """
    if "BAZEL_TEST" not in os.environ:
        return Path(arg)

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Failed to locate runfiles")
    return _rlocation(runfiles, arg)


def _extra_search_paths() -> list[str]:
    """Extract module resolution paths from ``sys.path`` for ty.

    The venv entrypoint has already populated ``sys.path`` with resolved
    absolute paths derived from ``PyInfo.imports`` and transitive deps.
    Since ty runs as a subprocess it cannot see these paths; we embed
    them via ``environment.extra-paths`` in a generated config so ty can
    resolve first-party imports (including those remapped via Bazel
    ``imports``) and third-party dependencies.
    """
    paths: list[str] = []
    seen: set[str] = set()
    for entry in sys.path:
        if not entry or entry in seen:
            continue
        if not os.path.isdir(entry):
            continue
        seen.add(entry)
        paths.append(entry)
    return paths


def _format_toml_value(value: object) -> str:
    """Format a Python value as a TOML literal.

    Paths are normalized to forward slashes so backslashes on Windows
    are not misinterpreted as TOML escape sequences.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        return f'"{normalized}"'
    if isinstance(value, list):
        inner = ", ".join(f'"{str(v).replace(chr(92), "/")}"' for v in value)
        return f"[{inner}]"
    return str(value)


def _strip_toml_section(raw: str, section: str) -> str:
    """Remove a top-level TOML section and its contents from raw text."""
    lines = raw.splitlines(keepends=True)
    result: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped == f"[{section}]":
            skipping = True
            continue
        if skipping and stripped.startswith("["):
            skipping = False
        if not skipping:
            result.append(line)
    return "".join(result)


def _generate_config(
    original_config: Path,
    extra_paths: Sequence[str],
    tmp_dir: Path,
) -> Path:
    """Generate a ty config with ``environment.extra-paths`` populated.

    Copies the user's ``ty.toml`` verbatim (preserving comments and
    formatting) with the ``[environment]`` section stripped, then
    appends a reconstructed ``[environment]`` containing all original
    keys plus the merged ``extra-paths``.  This keeps the ty command
    line constant-size regardless of the number of search paths.

    Args:
        original_config: Path to the user's ty config file.
        extra_paths: Absolute search paths derived from ``sys.path``.
        tmp_dir: Temporary directory for the generated config.

    Returns:
        Path to the generated config file.
    """
    raw = original_config.read_text(encoding="utf-8")

    with open(original_config, "rb") as f:
        config = tomllib.load(f)

    env = dict(config.get("environment", {}))
    existing = env.pop("extra-paths", [])

    seen = set(extra_paths)
    all_paths = list(extra_paths)
    for entry in existing:
        if entry not in seen:
            seen.add(entry)
            all_paths.append(entry)

    env["extra-paths"] = all_paths

    stripped = _strip_toml_section(raw, "environment")

    merged = tmp_dir / "ty.toml"
    with open(merged, "w", encoding="utf-8") as f:
        f.write(stripped)
        f.write("\n[environment]\n")
        for key, value in env.items():
            f.write(f"{key} = {_format_toml_value(value)}\n")
    return merged


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser("ty Runner")

    parser.add_argument(
        "--config",
        required=True,
        type=_maybe_runfile,
        help="The configuration file (`ty.toml`).",
    )
    parser.add_argument(
        "--ty",
        type=_maybe_runfile,
        default=None,
        help="The `ty` binary.",
    )
    parser.add_argument(
        "--marker",
        type=_maybe_runfile,
        help="The file to create as an indication that the 'ty' action succeeded.",
    )
    parser.add_argument(
        "--src",
        dest="sources",
        action="append",
        type=_maybe_runfile,
        required=True,
        help="A source file to run ty on.",
    )

    parsed_args = parser.parse_args(args)

    if not parsed_args.sources:
        parser.error("No source files were provided.")

    return parsed_args


def _load_args() -> Sequence[str]:
    """Load command line arguments from the environment."""
    if "BAZEL_TEST" in os.environ and "RULES_VENV_TY_RUNNER_ARGS_FILE" in os.environ:
        runfiles = Runfiles.Create()
        if not runfiles:
            raise EnvironmentError("Failed to locate runfiles")
        arg_file = _rlocation(runfiles, os.environ["RULES_VENV_TY_RUNNER_ARGS_FILE"])
        return arg_file.read_text(encoding="utf-8").splitlines()

    return sys.argv[1:]


def find_ty(ty_path: Optional[Path] = None) -> Path:
    """Locate ty from the python environment

    Args:
        ty_path: An override to enforce the desired binary.

    Returns:
        The path to the ty binary to use.
    """

    if ty_path is None:
        try:
            # pylint: disable-next=import-outside-toplevel
            import ty  # type: ignore

            try:
                ty_str = ty.find_ty_bin()
                if ty_str:
                    ty_path = Path(ty_str)
            except (FileNotFoundError, AttributeError):
                ty_module_path = Path(ty.__file__)
                ty_site_packages = ty_module_path.parent.parent
                ty_version = None
                for entry in ty_site_packages.iterdir():
                    if entry.name.endswith(".data"):
                        _, _, ty_version = entry.name[: -len(".data")].partition("-")
                        break

                if ty_version:
                    ty_scripts_dir = ty_site_packages / f"ty-{ty_version}.data/scripts"

                    ty_path = ty_scripts_dir / "ty"
                    if not ty_path.exists():
                        ty_path = ty_scripts_dir / "ty.exe"

        except ImportError as exc:
            raise ModuleNotFoundError(
                "No ty binary was provided and ty is not importable"
            ) from exc

    if not ty_path:
        raise FileNotFoundError("Failed to locate ty binary.")

    return ty_path


def main() -> None:
    """The main entrypoint."""
    args = parse_args(_load_args())

    stream = io.StringIO()

    ty = find_ty(args.ty)

    is_test = "BAZEL_TEST" in os.environ

    tmp_dir = tempfile.mkdtemp(prefix="bazel-ty-", dir=os.getenv("TEST_TMPDIR"))

    config_file = _generate_config(
        original_config=args.config,
        extra_paths=_extra_search_paths(),
        tmp_dir=Path(tmp_dir),
    )

    ty_args = [
        str(ty),
        "check",
        "--config-file",
        str(config_file),
    ]

    ty_args.extend([str(src) for src in args.sources])

    env = {
        "HOME": str(tmp_dir),
        "USERPROFILE": str(tmp_dir),
    }

    if "RULES_VENV_TY_DEBUG" in os.environ:
        ty_args.append("--verbose")

    result = subprocess.run(
        ty_args,
        stdout=None if is_test else subprocess.PIPE,
        stderr=None if is_test else subprocess.STDOUT,
        env=env,
        check=False,
    )
    if not is_test:
        stream.write(result.stdout.decode("utf-8"))

    if "TEST_TMPDIR" not in os.environ:
        shutil.rmtree(tmp_dir)

    if args.marker:
        if result.returncode == 0:
            args.marker.write_bytes(b"")
        else:
            print(stream.getvalue(), file=sys.stderr)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
