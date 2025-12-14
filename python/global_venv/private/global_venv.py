"""Generates a venv which includes all active python Bazel targets in a workspace."""

import argparse
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import venv
from dataclasses import Field, dataclass, fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence

SPEC_FILE_SUFFIX = ".py_global_venv_info.json"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--bazel", type=str, default="bazel", help="The path to a Bazel binary"
    )
    parser.add_argument("--dir", type=Path, help="The path of the venv to create.")
    parser.add_argument(
        "targets",
        type=str,
        default=["//..."],
        nargs="*",
        help="Space separated list of target patterns that comes after all other args.",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=False, help="Enable verbose logging."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="If set, any existing venv will be deleted.",
    )

    return parser.parse_args()


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
        self.interpreter: Optional[Path] = None

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

        # `BUILD_WORKSPACE_DIRECTORY` is checked in `main`
        repo_root = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])

        pth_data = []
        for pth in self.bazel_pth:
            abs_pth = Path(pth.format(runfiles_dir=repo_root))
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


def _bazel_env() -> Dict[str, str]:
    """Sanitize a map of environment variables for Bazel subprocesses.

    Returns:
        A map of environment variables.
    """
    env = dict(os.environ)
    for remove in (
        "BAZELISK_SKIP_WRAPPER",
        "BUILD_WORKING_DIRECTORY",
        "BUILD_WORKSPACE_DIRECTORY",
    ):
        if remove in env:
            del env[remove]
    return env


@dataclass(frozen=True)
class BazelInfo:
    """A class for `bazel info` outputs."""

    execution_root: Path
    output_base: Path


def get_bazel_info(bazel: Path | str, workspace_dir: Path | str) -> BazelInfo:
    """Query a workspace directory for Bazel info

    Args:
        bazel: The Bazel binary to use.
        workspace_dir: The path to the Bazel workspace.

    Returns:
        Deserialized Bazel info.
    """
    logging.debug("Bazel info...")
    args = [
        str(bazel),
        "info",
    ]
    logging.debug(" ".join(args))
    result = subprocess.run(
        args,
        env=_bazel_env(),
        check=True,
        encoding="utf-8",
        cwd=workspace_dir,
        capture_output=True,
    )
    logging.debug("%s", result.stdout)
    logging.debug("%s", result.stderr)
    logging.debug("Done.")

    info = {}
    supported_fields = [f.name for f in fields(BazelInfo)]
    for line in result.stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        key, _, value = text.partition(": ")
        if key not in supported_fields:
            continue
        info[key] = Path(value)

    return BazelInfo(**info)


def generate_global_venv_specs(
    bazel: Path | str,
    workspace_dir: Path | str,
    rules_venv_name: str,
    targets: List[str],
) -> None:
    """Invoke a Bazel build to generate "global venv" spec files.

    Args:
        bazel: The Bazel binary to use.
        workspace_dir: The path to the Bazel workspace.
        rules_venv_name: The `rules_venv` repository label part.
        targets: Targets to generate specs for.
    """
    logging.debug("Building specs...")
    args = [
        str(bazel),
        "build",
        rf"--aspects={rules_venv_name}//python/global_venv:defs.bzl%py_global_venv_aspect",
        "--output_groups=py_global_venv_info",
    ] + targets
    logging.debug(" ".join(args))
    subprocess.run(
        args,
        env=_bazel_env(),
        check=True,
        encoding="utf-8",
        cwd=workspace_dir,
        capture_output=logging.getLogger().level != logging.DEBUG,
    )
    logging.debug("Done.")


def map_data_fields(
    class_fields: Sequence[Field[Any]], field_map: Dict[str, str], data: Dict[str, Any]
) -> Dict[str, Any]:
    """A helper for deserializing aquery jsonproto outputs.

    For the purposes of the global venv maker, not all fields are needed
    from aquery output so in order to correctly construct the them this
    helper will prune unnecessary fields as well as handle name mapping
    for field names that are not pythonic.

    Args:
        class_fields: A list of dataclass fields
        field_map: A mapping of aquery field names to `class_fields` names.
        data: The data to deserialize

    Returns:
        Constructor data for a dataclass
    """
    result = {}
    for field in class_fields:
        if field.name in data:
            result[field.name] = data[field.name]
    for field, mapped in field_map.items():  # type: ignore
        if field in data:  # type: ignore
            result[mapped] = data[field]  # type: ignore
    return result


@dataclass(frozen=True)
class Artifact:
    """[analysis.proto Artifact](https://github.com/bazelbuild/bazel/blob/7.3.1/src/main/protobuf/analysis_v2.proto#L36-L38)"""

    id: int
    path_fragment_id: int

    @staticmethod
    def map_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize raw data for deserialization."""
        return map_data_fields(
            class_fields=fields(Artifact),
            field_map={
                "pathFragmentId": "path_fragment_id",
            },
            data=data,
        )


@dataclass(frozen=True)
class PathFragment:
    """[analysis.proto PathFragment](https://github.com/bazelbuild/bazel/blob/7.3.1/src/main/protobuf/analysis_v2.proto#L242-L243)"""

    id: int
    label: str
    parent_id: Optional[int] = None

    @staticmethod
    def map_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize raw data for deserialization."""
        return map_data_fields(
            class_fields=fields(PathFragment),
            field_map={
                "parentId": "parent_id",
            },
            data=data,
        )


@dataclass(frozen=True)
class Action:
    """[analysis.proto Action](https://github.com/bazelbuild/bazel/blob/7.3.1/src/main/protobuf/analysis_v2.proto#L52-L54)"""

    output_ids: Sequence[int]

    @staticmethod
    def map_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize raw data for deserialization."""
        return map_data_fields(
            class_fields=fields(Action),
            field_map={"outputIds": "output_ids"},
            data=data,
        )


@dataclass(frozen=True)
class ActionGraphContainer:
    """[analysis.proto ActionGraphContainer](https://github.com/bazelbuild/bazel/blob/7.3.1/src/main/protobuf/analysis_v2.proto#L24-L25C9)"""

    artifacts: Sequence[Artifact]
    actions: Sequence[Action]
    path_fragments: Sequence[PathFragment]


def deserialize_aquery_output(jsonproto: Dict[str, Any]) -> ActionGraphContainer:
    """Deserialize aquery output into python classes.

    Args:
        jsonproto: Deserialized json data.

    Returns:
        Deserialized aquery output.
    """
    if not jsonproto:
        raise ValueError("The jsonproto cannot be empty.")
    if "actions" not in jsonproto:
        logging.warning(
            "Aquery jsonproto has no `actions` key. Results may be affected"
        )
    if "artifacts" not in jsonproto:
        logging.warning(
            "Aquery jsonproto has no `artifacts` key. Results may be affected"
        )
    if "pathFragments" not in jsonproto:
        logging.warning(
            "Aquery jsonproto has no `pathFragments` key. Results may be affected"
        )
    raw_actions = jsonproto.get("actions", [])
    raw_artifacts = jsonproto.get("artifacts", [])
    raw_fragments = jsonproto.get("pathFragments", [])
    if not raw_actions:
        logging.warning("Aquery jsonproto has `actions`. Results may be affected")
    if not raw_artifacts:
        logging.warning("Aquery jsonproto has `artifacts`. Results may be affected")
    if not raw_fragments:
        logging.warning(
            "Aquery jsonproto has no `pathFragments`. Results may be affected"
        )
    actions = [
        Action(**Action.map_fields(entry)) for entry in jsonproto.get("actions", [])
    ]
    artifacts = [
        Artifact(**Artifact.map_fields(entry))
        for entry in jsonproto.get("artifacts", [])
    ]
    path_fragments = [
        PathFragment(**(PathFragment.map_fields(entry)))
        for entry in jsonproto.get("pathFragments", [])
    ]

    return ActionGraphContainer(
        actions=actions,
        artifacts=artifacts,
        path_fragments=path_fragments,
    )


def path_from_fragments(frag_id: int, fragments: Dict[int, PathFragment]) -> Path:
    """Recursively compute the a path from a map of path fragments

    Args:
        frag_id: The id to build a path for
        fragments: A mapping of path id's to fragments.

    Returns:
        The constructed path.
    """
    if frag_id not in fragments:
        raise KeyError("internal consistency error in bazel output")

    fragment = fragments[frag_id]

    path = Path(fragment.label)

    if fragment.parent_id:
        parent = path_from_fragments(fragment.parent_id, fragments)
        path = Path(parent) / path

    return path


@dataclass(frozen=True)
class PyGlobalVenvInfo:
    """A python implementation of the Bazel provider."""

    imports: Sequence[str]
    bin_dir: Optional[Path] = None


def query_global_venv_specs(
    bazel: Path | str,
    workspace_dir: Path | str,
    rules_venv_name: str,
    targets: List[str],
    execution_root: Path | str,
) -> Sequence[Path]:
    """Perform a Bazel query and return paths to `PyGlobalVenvInfo` spec files.

    Args:
        bazel: The path to a Bazel binary.
        workspace_dir: The path to the Bazel workspace to query.
        rules_venv_name: The name of the `rules_venv` repository. Varies when run
            within the `rules_venv` repo.
        targets: Targets to query. Can include recursive `//...` pattern.
        execution_root: The path to the Bazel execution root.

    Returns:
        A list of absolute paths to json encoded `PyGlobalVenvInfo` data.
    """

    env = dict(os.environ)
    for remove in (
        "BAZELISK_SKIP_WRAPPER",
        "BUILD_WORKING_DIRECTORY",
        "BUILD_WORKSPACE_DIRECTORY",
    ):
        if remove in env:
            del env[remove]

    with tempfile.TemporaryDirectory(prefix="rules_venv_global-") as tmp:
        tmp_log = Path(tmp) / "aquery_log.json"
        logging.debug("Querying specs...")
        args = [
            str(bazel),
            "aquery",
            "--include_aspects",
            "--include_artifacts",
            rf"--aspects={rules_venv_name}//python/global_venv:defs.bzl%py_global_venv_aspect",
            "--noinclude_commandline",
            "--output_groups=py_global_venv_info",
            "--output=jsonproto",
            f"--output_file={tmp_log}",
        ] + targets
        logging.debug(" ".join(args))
        subprocess.run(
            args,
            env=_bazel_env(),
            check=True,
            encoding="utf-8",
            cwd=workspace_dir,
            capture_output=True,
        )
        logging.debug("Done.")

        with tmp_log.open() as log:
            aquery_output = deserialize_aquery_output(jsonproto=json.load(log))

        path_fragments = {frag.id: frag for frag in aquery_output.path_fragments}

        spec_paths = [
            Path(execution_root)
            / path_from_fragments(artifact.path_fragment_id, path_fragments)
            for artifact in aquery_output.artifacts
            if path_fragments[artifact.path_fragment_id].label.endswith(
                SPEC_FILE_SUFFIX
            )
        ]

        # This can occur if there are no python targets or if targets are using the native
        # `PyInfo` which will not match the expectations of the aspect. `rules_python >= 1.5.0`
        # should be used to provide `PyInfo`.
        if not spec_paths:
            logging.warning(
                "No spec paths were found which means the venv will be empty."
            )

        return sorted(set(spec_paths))


def load_specs(spec_paths: Sequence[Path]) -> Sequence[PyGlobalVenvInfo]:
    """Deserialize a list of `PyGlobalVenvInfo` spec files.

    Args:
        spec_paths: The path to json encoded spec files.

    Returns:
        Deserialized `PyGlobalVenvInfo` providers.
    """
    specs = [
        PyGlobalVenvInfo(**json.loads(path.read_text(encoding="utf-8")))
        for path in spec_paths
    ]
    return specs


def get_pth(
    specs: Sequence[PyGlobalVenvInfo],
    execution_root: Path,
    output_base: Path,
    workspace_dir: Path,
    workspace_name: str,
) -> Sequence[str]:
    """Determine the Python `pth` from a workspace's python targets.

    Args:
        specs: Deserialized `PyGlobalVenvInfo` providers for each python target.
        execution_root: The path to the Bazel execution root.
        output_base: The path to the Bazel output base.
        workspace_dir: The path to the Bazel workspace
        workspace_name: The name of the current Bazel workspace.

    Returns:
        A list of paths to include in a `pth` file.
    """
    # There is no ordered set in python so a dict is used for it's index behavior.
    pth: Dict[str, None] = {}
    for spec in specs:
        for i in spec.imports:
            if i == workspace_name:
                pth[str(workspace_dir)] = None
                if spec.bin_dir:
                    pth[str(execution_root / spec.bin_dir)] = None
            elif i.startswith(f"{workspace_name}/"):
                _, _, i = i.partition("/")
                pth[str(workspace_dir / i)] = None
                if spec.bin_dir:
                    pth[str(execution_root / spec.bin_dir / i)] = None
            else:
                pth[str(output_base / "external" / i)] = None
                if spec.bin_dir:
                    pth[str(execution_root / spec.bin_dir / "external" / i)] = None

    return list(pth.keys())


def main() -> None:
    """The main entrypoint."""
    if "BUILD_WORKSPACE_DIRECTORY" not in os.environ:
        # Running outside of Bazel?
        raise EnvironmentError(
            "BUILD_WORKSPACE_DIRECTORY is not set in the environment."
        )

    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
    )

    workspace = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    bazel = args.bazel
    targets = args.targets

    venv_dir = workspace / ".venv"
    if args.dir:
        if not args.dir.is_absolute():
            cwd = Path(os.environ["BUILD_WORKING_DIRECTORY"])
            venv_dir = cwd / args.dir
        else:
            venv_dir = args.dir

    if venv_dir.exists() and args.clean:
        logging.debug("Cleaning existing venv: %s", venv_dir)
        shutil.rmtree(venv_dir)

    bazel_info = get_bazel_info(bazel=bazel, workspace_dir=workspace)

    # If the workspace has no name then use the name of the workspace directory.
    workspace_name = bazel_info.execution_root.name
    if workspace_name == "__main__":
        workspace_name = workspace.name

    rules_venv_name = "@rules_venv"
    if workspace_name == "rules_venv":
        rules_venv_name = "@"

    # Generate venv specs
    generate_global_venv_specs(
        bazel=bazel,
        workspace_dir=workspace,
        rules_venv_name=rules_venv_name,
        targets=targets,
    )

    # Collect all venv targets
    spec_paths = query_global_venv_specs(
        bazel=bazel,
        workspace_dir=workspace,
        rules_venv_name=rules_venv_name,
        targets=targets,
        execution_root=bazel_info.execution_root,
    )

    specs = load_specs(spec_paths=spec_paths)

    # Use `venv_maker` to create a venv in `BUILD_WORKSPACE_DIRECTORY`
    venv_interpreter = create_venv(
        venv_name=workspace_name,
        venv_dir=venv_dir,
        pth=get_pth(
            specs=specs,
            execution_root=bazel_info.execution_root,
            output_base=bazel_info.output_base,
            workspace_dir=workspace,
            workspace_name=bazel_info.execution_root.name,
        ),
    )

    is_windows = platform.system() == "Windows"
    activate_script = "activate.bat" if is_windows else "activate"
    activate_path = venv_interpreter.parent / activate_script

    if is_windows:
        logging.info(
            "Generation complete, to activate run:\n\t%s",
            activate_path,
        )
    else:
        logging.info(
            "Generation complete, to activate run:\n\tsource %s",
            activate_path,
        )


if __name__ == "__main__":
    main()
