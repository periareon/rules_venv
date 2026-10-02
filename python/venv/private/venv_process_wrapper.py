"""The `rules_venv` process wrapper for all executables.

This script is responsible for building a venv and running the
main entrypoint provided by the Bazel rule.
"""

import functools
import hashlib
import json
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import venv
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

_LOG = logging.getLogger(__name__)

_EXTRACT_ROOT_VARS = ("RULES_VENV_EXTRACT_ROOT", "RULES_PYTHON_EXTRACT_ROOT")
"""Environment variables naming a persistent root for venvs, in priority order."""

_STAMP_NAME = "rules_venv.stamp.json"
"""The file written into each directory this wrapper builds, recording its key."""


class ParsedArgs(NamedTuple):
    """A fast alternative to `argparse.Namespace`."""

    venv_config: Path
    """The path to the rules_venv config file for the current target."""

    main: Path
    """The target's entrypoint."""

    main_args: Sequence[str]
    """Arguments to pass to `main`."""


def parse_args() -> ParsedArgs:
    """Parse command line arguments."""

    return ParsedArgs(
        venv_config=Path(sys.argv[1]),
        main=Path(sys.argv[2]),
        main_args=sys.argv[3:],
    )


def runfiles_dir() -> Path:
    """Determine the absolute runfiles directory for the current process."""
    if "RULES_VENV_RUNFILES_DIR" in os.environ:
        runfiles_path = Path(os.environ["RULES_VENV_RUNFILES_DIR"])
    else:
        runfiles_path = Path(os.environ["RUNFILES_DIR"])

    if not runfiles_path.is_absolute():
        runfiles_path = Path.cwd() / runfiles_path

    return runfiles_path


class ExtendedEnvBuilder(venv.EnvBuilder):
    """https://docs.python.org/3/library/venv.html"""

    def __init__(
        self,
        name: str,
        pth: Sequence[str],
    ) -> None:
        """Constructor.

        Args:
            name: The name of the venv (prompt).
            pth: The `pth` values to add to PYTHONPATH. Note that each value
                can contain a format string `{runfiles_dir}` that will be
                substituted out.
        """
        self.bazel_pth = pth
        self.interpreter: Path | None = None

        super().__init__(
            system_site_packages=False,
            clear=False,
            upgrade=False,
            with_pip=False,
            symlinks=True,
            prompt=name,
            upgrade_deps=False,
        )

    def post_setup(self, context: SimpleNamespace) -> None:
        """
        Set up any packages which need to be pre-installed into the
        virtual environment being created.

        https://docs.python.org/3/library/site.html

        Args:
            context: The information for the virtual environment
                creation request being processed.
        """
        self.interpreter = Path(context.env_exe)

        major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
        if platform.system() == "Windows":
            site_packages = Path(context.env_dir) / "Lib/site-packages"
        else:
            site_packages = (
                Path(context.env_dir) / f"lib/python{major_minor}/site-packages"
            )

        if not site_packages:
            raise FileNotFoundError(
                f"Failed to find site-packages directory at {site_packages}"
            )

        runfiles_path = runfiles_dir()

        pth_data = []
        for pth in self.bazel_pth:
            abs_pth = Path(pth.format(runfiles_dir=runfiles_path))

            # `site` silently drops a `.pth` line whose directory does
            # not exist, so a root that nothing happens to stage a file
            # under would leave the venv without it. Creating it keeps
            # the venv's import paths a function of what was asked for
            # rather than of what else landed there, which is what lets a
            # caller stage files under a root after the venv is built.
            #
            # Only within the runfiles tree, which is either a Bazel
            # output or this wrapper's own temp directory. A root can
            # also name a repository read in place from where it was
            # fetched, and creating directories there would edit the
            # fetched sources -- or fail where they are not writable.
            if abs_pth.is_relative_to(runfiles_path):
                abs_pth.mkdir(parents=True, exist_ok=True)

            pth_data.append(str(abs_pth))

        pth_file = site_packages / "rules_venv.pth"
        pth_file.write_text(
            "\n".join(pth_data) + "\n",
            encoding="utf-8",
        )


def create_venv(
    venv_name: str,
    venv_dir: Path | str,
    pth: Sequence[str],
) -> Path:
    """Construct a new Python venv at the requested location.

    Args:
        venv_name: The name (prompt) of the venv.
        venv_dir: The location where the venv should be created
        pth: Values to add to the a `pth` file for import resolution.

    Returns:
        The path to the new venv interpreter.
    """
    builder = ExtendedEnvBuilder(
        name=venv_name,
        pth=pth,
    )

    builder.create(venv_dir)

    interpreter = builder.interpreter
    if not interpreter:
        raise RuntimeError("Failed to locate venv interpreter")

    return interpreter


def extract_zip(zip_file: Path, output_dir: Path) -> None:
    """A helper for extracting a zip file and maintaining file permissions

    Args:
        zip_file: The zip file to extract
        output_dir: The output location
    """
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        for info in zip_ref.infolist():
            extracted_path = zip_ref.extract(info, output_dir)

            zip_unix_system = 3
            if info.create_system == zip_unix_system:
                unix_attributes = info.external_attr >> 16
                if unix_attributes:
                    os.chmod(extracted_path, unix_attributes)


def install_files(
    manifest: Path, output_dir: Path, src_root: Path | None = None
) -> None:
    """A helper for installing files in a directory.

    Args:
        manifest: The manifest to use for installing files. Expected to be a json
            encoded map of source paths to rlocationpaths
        output_dir: The output directory in which to install files.
        src_root: The root from which all source files in `manifest` are relative to.
    """

    def link(src: Path, dest: Path) -> None:
        """Symlink `dest` to `src`."""
        dest.symlink_to(src)

    def copy(src: Path, dest: Path) -> None:
        """Copy `src` to `dest`."""
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

    install_fn = link

    # Using symlinks on windows is both not guaranteed and can have
    # significant performance impacts at runtime. Some profiling
    # observed the time it takes to copy files is over all less than
    # the time lost in runtime with symlinks.
    if platform.system() == "Windows":
        install_fn = copy

    pairs = json.loads(manifest.read_text(encoding="utf-8"))

    if "RUNFILES_MANIFEST_FILE" in os.environ:
        runfiles = {}
        for line in (
            Path(os.environ["RUNFILES_MANIFEST_FILE"])
            .read_text(encoding="utf-8")
            .splitlines()
        ):
            rlocation, _, real_path = line.strip().partition(" ")
            runfiles[rlocation.replace("\\s", " ")] = real_path

        for dest in pairs.values():
            abs_src = Path(runfiles[dest])
            abs_dest = output_dir / dest
            abs_dest.parent.mkdir(exist_ok=True, parents=True)
            install_fn(abs_src, abs_dest)

    else:
        if src_root is None:
            src_root = Path.cwd()

        for src, dest in pairs.items():
            abs_src = src_root / src
            abs_dest = output_dir / dest
            abs_dest.parent.mkdir(exist_ok=True, parents=True)
            install_fn(abs_src, abs_dest)


def _restore_sigint() -> None:
    """Restore SIGINT to SIG_DFL. Used as `preexec_fn` for child processes."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def rmtree(path: Path | str) -> None:
    """Attempt to delete a directory tree."""
    # Here we use `TemporaryDirectory` to wrap the path to delete and delete it.
    # Internally this will spawn an additional temp directory inside of `path`
    # but this should not matter as the parent directory will immediately be cleaned up.
    # pylint: disable-next=consider-using-with
    wrapper = tempfile.TemporaryDirectory(dir=path)

    # Override the path represented by `TemporaryDirectory`
    wrapper.name = str(path)

    # Cleanup the parent directory.
    wrapper.cleanup()


def find_extract_root() -> Path | None:
    """Locate a persistent root for venvs from the environment.

    `RULES_VENV_EXTRACT_ROOT` takes priority over `RULES_PYTHON_EXTRACT_ROOT`.
    A relative root is resolved against the current working directory.
    """
    for var in _EXTRACT_ROOT_VARS:
        value = os.environ.get(var)
        if value:
            _LOG.debug("Using extract root from %s: %s", var, value)
            return Path.cwd() / value

    return None


def label_to_path(label: str) -> Path:
    """Convert `@@repo//pkg:name` to `repo/pkg/name`, using `_main` for the main repo."""
    repo, _, rest = label.lstrip("@").partition("//")
    package, _, name = rest.partition(":")
    return Path(repo or "_main") / package / name


def digest(parts: Sequence[str]) -> str:
    """Hash a sequence of strings into a key."""
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _read_stamp(directory: Path) -> dict[str, str] | None:
    """Read the stamp left in a directory built by `prepare_dir`, if any."""
    try:
        stamp = json.loads((directory / _STAMP_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    return stamp if isinstance(stamp, dict) else None


def prepare_dir(
    dest: Path, key: str, build: Callable[[Path], dict[str, str]]
) -> dict[str, str]:
    """Populate `dest` using `build`, or reuse it if it was built from `key`.

    `build` is run on a staging directory which is then renamed into place,
    so a concurrent launch never observes a half-built `dest`.

    Args:
        dest: The directory to prepare.
        key: A key identifying everything the directory's contents depend on.
        build: Populates a directory and returns extra data to stamp it with.

    Returns:
        The stamp of the directory now at `dest`.
    """
    stamp = _read_stamp(dest)
    if stamp and stamp.get("key") == key:
        _LOG.debug("Reusing: %s", dest)
        return stamp

    if dest.exists():
        _LOG.debug("Replacing stale: %s", dest)
        rmtree(dest)

    dest.parent.mkdir(exist_ok=True, parents=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{dest.name}.tmp-", dir=dest.parent))
    stamp = {"key": key, **build(staging)}
    (staging / _STAMP_NAME).write_text(json.dumps(stamp, indent=4), encoding="utf-8")

    try:
        os.rename(staging, dest)
    except OSError:
        # A concurrent launch published an equivalent directory first.
        existing = _read_stamp(dest)
        if not existing or existing.get("key") != key:
            raise
        rmtree(staging)
        stamp = existing

    return stamp


def render_runfiles(collection: Path, output_dir: Path) -> dict[str, str]:
    """Render a runfiles collection into `output_dir`."""
    if collection.suffix == ".zip":
        _LOG.debug("Extracting runfiles collection to: %s", output_dir)
        extract_zip(zip_file=collection, output_dir=output_dir)
    elif collection.suffix == ".json":
        _LOG.debug("Linking runfiles collection to: %s", output_dir)
        install_files(manifest=collection, output_dir=output_dir)
    else:
        raise OSError(
            f"Unexpected `RULES_VENV_RUNFILES_COLLECTION` value: {collection}"
        )

    return {}


def build_venv(venv_name: str, pth: Sequence[str], output_dir: Path) -> dict[str, str]:
    """Create a venv in `output_dir`, recording where its interpreter is."""
    _LOG.debug("Creating venv at: %s", output_dir)
    interpreter = create_venv(venv_name=venv_name, venv_dir=output_dir, pth=pth)
    return {"interpreter": interpreter.relative_to(output_dir).as_posix()}


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    if (
        "RULES_VENV_PROCESS_WRAPPER_DEBUG" in os.environ
        or "RULES_VENV_DEBUG" in os.environ
    ):
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            level=logging.DEBUG,
        )

    config = json.loads(args.venv_config.read_text(encoding="utf-8"))
    label = config["label"]

    # With an extract root, the venv (and any rendered runfiles) live at a
    # predictable location under it, are reused by later launches and are
    # never deleted here, so `sys.executable` stays valid after this process
    # exits. Cleaning up the root is the caller's responsibility.
    #
    # Otherwise the new venv is only a couple of files and directories, cleaning
    # it up should be fast so it's written to a temp directory.
    temp_dir: Path | None = None
    extract_root = find_extract_root()
    if extract_root:
        target_dir = extract_root / label_to_path(label)
        venv_dir = target_dir.with_name(target_dir.name + ".venv")
        runfiles_dest = target_dir.with_name(target_dir.name + ".runfiles")
    else:
        temp_dir = Path(
            tempfile.mkdtemp(
                prefix=f"venv-{config['name']}-",
                dir=os.getenv("TEST_TMPDIR"),
            )
        )
        venv_dir = temp_dir / "venv"
        runfiles_dest = temp_dir / "runfiles"

    # If a runfiles collection was passed, always use it in place of any
    # pre-defined runfiles directories.
    if "RULES_VENV_RUNFILES_COLLECTION" in os.environ:
        collection = Path(os.environ["RULES_VENV_RUNFILES_COLLECTION"])
        stat = collection.stat()
        prepare_dir(
            dest=runfiles_dest,
            key=digest([str(collection), str(stat.st_size), str(stat.st_mtime_ns)]),
            build=functools.partial(render_runfiles, collection),
        )
        os.environ["RULES_VENV_RUNFILES_DIR"] = str(runfiles_dest)

        _LOG.debug("Runfiles ready!")

    # The venv dir is only cleaned up if the target is not running under
    # a Bazel test. Bazel will clean up the directory for us when the test
    # finishes.
    try:
        config_pth = config["pth"]

        # For static repos (all-source, no generated files), rewrite their
        # .pth entries to reference the external directory on disk directly
        # instead of going through the extracted runfiles collection.
        static_repos = config.get("static_repos", [])
        if static_repos:
            external_dir = None
            for parent in Path(sys.executable).parents:
                if parent.name == "external":
                    external_dir = parent
                    break

            if external_dir:
                for repo_name in static_repos:
                    for idx, entry in enumerate(config_pth):
                        if ("{runfiles_dir}/" + repo_name) in entry:
                            config_pth[idx] = entry.format(runfiles_dir=external_dir)

        # Create a new venv, or reuse one built from the same inputs.
        stamp = prepare_dir(
            dest=venv_dir,
            key=digest(
                [label, sys.executable, sys.version, str(runfiles_dir()), *config_pth]
            ),
            build=functools.partial(build_venv, label, config_pth),
        )
        venv_interpreter = venv_dir / stamp["interpreter"]

        # Subprocess the entrypoint via the new venv.
        main_args: list[str] = [
            str(venv_interpreter),
            "-B",  # don't write .pyc files on import; also PYTHONDONTWRITEBYTECODE=x
            "-s",  # don't add user site directory to sys.path; also PYTHONNOUSERSITE
        ]
        if sys.version_info >= (3, 11):
            main_args.append("-P")  # safe paths (available in Python 3.11)
        main_args.append(str(args.main))
        main_args.extend(args.main_args)

        _LOG.debug("Spawning subprocess: %s", " ".join(main_args))

        # Ignore SIGINT in the wrapper so Ctrl+C is handled entirely by the
        # child (e.g. Jupyter's interactive shutdown prompt). On POSIX,
        # Popen's `restore_signals` does not cover SIGINT and CPython
        # preserves an inherited SIG_IGN instead of installing its default
        # KeyboardInterrupt handler, so restore SIG_DFL in the child via
        # `preexec_fn`. Windows does not inherit SIG_IGN across processes.
        popen_kwargs = {}
        if platform.system() != "Windows":
            popen_kwargs["preexec_fn"] = _restore_sigint
        old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        proc = subprocess.Popen(main_args, **popen_kwargs)
        returncode = proc.wait()
        signal.signal(signal.SIGINT, old_handler)
        _LOG.debug("Process complete with exit code: %d", returncode)
        sys.exit(returncode)
    finally:
        # An extract root is left in place for the caller to manage.
        skip_cleanup = temp_dir is None

        # https://bazel.build/reference/test-encyclopedia#initial-conditions
        # TEST_TMPDIR: Is defined whenever running in under `bazel test`.
        skip_cleanup = "TEST_TMPDIR" in os.environ or skip_cleanup

        # Allow users to explicitly prevent cleanup
        skip_cleanup = (
            "RULES_VENV_PROCESS_WRAPPER_LEAK_VENV" in os.environ or skip_cleanup
        )

        if skip_cleanup or temp_dir is None:
            _LOG.debug("Skipping cleanup of: %s", venv_dir)
        else:
            try:
                rmtree(temp_dir)
            except (PermissionError, OSError) as exc:
                _LOG.warning(
                    "Error encountered while cleaning up venv %s: %s", temp_dir, exc
                )


if __name__ == "__main__":
    main()
