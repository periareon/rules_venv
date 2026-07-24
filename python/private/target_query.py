"""Shared target-discovery helpers for the Python formatters and fixers.

Uses `bazel query` in loading phase (never `cquery` or `build`, so
targets marked incompatible with the host platform are not silently
dropped) to return per-target metadata:

- label / package
- `.py` source files reachable via `srcs` and `main` at the target itself
  (never `data`), with all downstream file-carrying attributes followed
  uniformly so filegroups (including nested and `data`-only filegroups
  reached via `srcs`) resolve correctly
- raw values of the `imports` attribute (needed by isort/ruff to compute
  first-party import paths)

Strategy is iterative BFS through only file-carrying attributes rather
than `deps(...)`. `deps(...)` follows every label attribute including
`deps` / `runtime_deps` / toolchain refs, which on large monorepos
materializes the entire transitive graph and OOMs Bazel. BFS confines
each round to the labels we actually need to walk (source files and
filegroups reachable via `srcs`/`main`/etc.) and is bounded by the
depth of filegroup nesting — typically 1-2 levels.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Sequence, Set, Tuple

from python.runfiles import Runfiles

# File-carrying attributes traversed below the PyInfo boundary. `deps` /
# `exports` / `runtime_deps` are intentionally excluded — dep targets get
# picked up on their own via the scope; the fixer scope determines what
# is formatted, not what a target depends on.
_SUBTREE_FILE_ATTRS: FrozenSet[str] = frozenset(("srcs", "main", "data"))

# Attributes read at the root of a PyInfo target itself. `data` is
# deliberately absent — this is the whole point of the boundary rule.
_ROOT_FILE_ATTRS: Tuple[str, ...] = ("srcs", "main")

_SOURCE_FILE_KIND = "__source_file__"


@dataclass(frozen=True)
class TargetInfo:
    """Metadata a formatter/fixer needs about a single Python target."""

    label: str
    package: str
    files: Tuple[str, ...]
    imports: Tuple[str, ...]


@dataclass
class _Entity:
    """Parsed record from `--output=streamed_jsonproto`."""

    label: str
    kind: str  # rule class, or `_SOURCE_FILE_KIND` for source files
    tags: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    attr_labels: Dict[str, List[str]] = field(default_factory=dict)


def find_bazel() -> Path:
    """Locate a Bazel executable."""
    if "BAZEL_REAL" in os.environ:
        return Path(os.environ["BAZEL_REAL"])

    for filename in ["bazel", "bazel.exe", "bazelisk", "bazelisk.exe"]:
        path = shutil.which(filename)
        if path:
            return Path(path)

    raise FileNotFoundError("Could not locate a Bazel binary")


def rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists."""
    # TODO: https://github.com/periareon/rules_venv/issues/37
    source_repo = None
    if platform.system() == "Windows":
        source_repo = ""
    runfile = runfiles.Rlocation(rlocationpath, source_repo)
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def query_python_targets(
    scope: Sequence[str],
    bazel: Path,
    workspace_dir: Path,
    *,
    ignore_tags: Sequence[str] = (),
) -> List[TargetInfo]:
    """Return every PyInfo-like target under `scope` with its resolved file set.

    A target counts as "Python-like" if the resolver walks at least one
    `.py` source file starting from its `srcs` or `main`. This is a
    loading-phase proxy for the `PyInfo` provider — we cannot ask
    `bazel query` about providers, and `cquery`/aspects would drop
    incompatible targets.

    `ignore_tags` values are normalized (`.replace("-","_").lower()`) so
    callers only need to list one spelling of each tag; matching against
    a target's tags is done in Python, not in the query, so there is no
    regex-escaping foot-gun.
    """
    entities: Dict[str, _Entity] = {}
    root_labels, scope_source_files = _fetch_roots(
        bazel, workspace_dir, scope, entities, ignore_tags
    )
    _bfs_file_subgraph(bazel, workspace_dir, root_labels, entities)
    return _build_target_infos(root_labels, scope_source_files, entities)


def _fetch_roots(
    bazel: Path,
    workspace_dir: Path,
    scope: Sequence[str],
    entities: Dict[str, _Entity],
    ignore_tags: Sequence[str],
) -> Tuple[List[str], List[_Entity]]:
    """Round 1: fetch scope roots + their attributes; split rules vs scope-level `.py`.

    Wildcards in `scope` are handled by Bazel here — no need to
    enumerate labels first. Tag filtering runs in Python against the
    streamed attribute data, not as an `attr(tags, ...)` regex, so
    there is no escaping/case foot-gun.
    """
    roots_query = f"set({' '.join(scope)})"
    root_labels: List[str] = []
    scope_source_files: List[_Entity] = []
    for entity in _stream_query(bazel, workspace_dir, roots_query):
        entities[entity.label] = entity
        if entity.kind == _SOURCE_FILE_KIND:
            # Only source files named directly in `scope` need to be
            # surfaced here — source files reached via BFS are already
            # attached to the parent rule they were pulled in through.
            if entity.label.startswith("//") and _label_to_path(entity.label).endswith(
                ".py"
            ):
                scope_source_files.append(entity)
        else:
            root_labels.append(entity.label)

    ignore_set = {_normalize_tag(t) for t in ignore_tags if t}
    if ignore_set:
        root_labels = [
            label
            for label in root_labels
            if not any(
                _normalize_tag(tag) in ignore_set for tag in entities[label].tags
            )
        ]
    return root_labels, scope_source_files


def _bfs_file_subgraph(
    bazel: Path,
    workspace_dir: Path,
    root_labels: Sequence[str],
    entities: Dict[str, _Entity],
) -> None:
    """Iteratively fetch labels reached via file-carrying attributes.

    First expansion uses only `_ROOT_FILE_ATTRS` at each root; every
    subsequent round uses `_SUBTREE_FILE_ATTRS`. Bounded by filegroup
    nesting depth — typically 1-2 rounds — so this is cheap even
    though each round is its own `bazel query` invocation.
    """
    to_fetch: Set[str] = set()
    for label in root_labels:
        entity = entities[label]
        for attr in _ROOT_FILE_ATTRS:
            for child in entity.attr_labels.get(attr, []):
                _enqueue(entities, to_fetch, child)

    while to_fetch:
        current = to_fetch
        to_fetch = set()
        _fetch_labels(bazel, workspace_dir, entities, current)
        for label in current:
            fetched = entities.get(label)
            if fetched is None or fetched.kind == _SOURCE_FILE_KIND:
                continue
            for attr in _SUBTREE_FILE_ATTRS:
                for child in fetched.attr_labels.get(attr, []):
                    _enqueue(entities, to_fetch, child)


def _build_target_infos(
    root_labels: Sequence[str],
    scope_source_files: Sequence[_Entity],
    entities: Dict[str, _Entity],
) -> List[TargetInfo]:
    results: List[TargetInfo] = []
    for label in root_labels:
        entity = entities[label]
        py_files = tuple(
            sorted(f for f in _resolve_files(entity, entities) if f.endswith(".py"))
        )
        if not py_files:
            continue
        results.append(
            TargetInfo(
                label=label,
                package=_label_package(label),
                files=py_files,
                imports=tuple(entity.imports),
            )
        )
    for source in scope_source_files:
        # Synthetic single-file entry so `//pkg:foo.py` scopes still get
        # formatted — the old query-based fixers accepted this shape.
        results.append(
            TargetInfo(
                label=source.label,
                package=_label_package(source.label),
                files=(_label_to_path(source.label),),
                imports=(),
            )
        )
    return results


def resolve_source_paths(
    scope: Sequence[str],
    bazel: Path,
    workspace_dir: Path,
    *,
    ignore_tags: Sequence[str] = (),
) -> List[str]:
    """Return every workspace-relative `.py` path in scope, sorted + deduped.

    Convenience wrapper for tools like ruff/black that don't need
    per-target metadata — just the flat file list.
    """
    targets = query_python_targets(
        scope=scope,
        bazel=bazel,
        workspace_dir=workspace_dir,
        ignore_tags=ignore_tags,
    )
    return sorted({file for target in targets for file in target.files})


def _normalize_tag(tag: str) -> str:
    """Fold BUILD-file tag spelling variants to a single form.

    Mirrors the check aspects' `tag.replace("-","_").lower()` so a target
    tagged `no-format`, `NO_FORMAT`, or `no_format` all compare equal.
    """
    return tag.replace("-", "_").lower()


def _enqueue(entities: Dict[str, _Entity], queue: Set[str], label: str) -> None:
    """Add a label to the BFS queue unless we've already handled it."""
    if not label or label.startswith("@"):
        # External sources are never formatted.
        return
    if label in entities or label in queue:
        return
    queue.add(label)


def _fetch_labels(
    bazel: Path,
    workspace_dir: Path,
    entities: Dict[str, _Entity],
    labels: Set[str],
) -> None:
    """Fetch attributes for `labels` in a single query.

    Uses `--query_file` rather than an inline expression so batches of
    tens of thousands of labels don't hit argv length limits.
    """
    if not labels:
        return
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".query",
        prefix="target_query_",
        encoding="utf-8",
        delete=False,
    ) as fh:
        # Labels can contain spaces / parens / other characters the query
        # lexer treats as syntax. Quoting every label sidesteps that —
        # inside a double-quoted label only `"` and `\` need escaping.
        fh.write(
            "set(" + " ".join(_quote_query_label(label) for label in labels) + ")\n"
        )
        query_file = fh.name
    try:
        for entity in _stream_query(bazel, workspace_dir, "--query_file=" + query_file):
            entities[entity.label] = entity
    finally:
        Path(query_file).unlink(missing_ok=True)


def _stream_query(
    bazel: Path, workspace_dir: Path, *query_argv: str
) -> Iterator[_Entity]:
    """Stream a `bazel query --output=streamed_jsonproto` result line by line.

    `query_argv` may be a single inline expression, `"--query_file=<path>"`,
    or any other tail of `bazel query` arguments. Callers pass exactly one
    query-source flag.
    """
    argv = [
        str(bazel),
        "query",
        *query_argv,
        "--noimplicit_deps",
        "--keep_going",
        "--output=streamed_jsonproto",
    ]

    # Popen + line iteration keeps memory constant instead of buffering
    # a potentially multi-hundred-MB jsonproto stream all at once.
    with subprocess.Popen(
        argv,
        cwd=str(workspace_dir),
        stdout=subprocess.PIPE,
        encoding="utf-8",
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            parsed = _parse_entity(json.loads(line))
            if parsed is not None:
                yield parsed
        process.wait()
        # 0 = clean success; 3 = `--keep_going` swallowed at least one
        # error but produced results for the rest. Any other exit means
        # bazel failed hard (syntax error, unresolvable scope, OOM, ...)
        # — the streamed output is incomplete and we must not silently
        # succeed.
        if process.returncode not in (0, 3):
            raise RuntimeError(
                "bazel query exited with code "
                f"{process.returncode}: {' '.join(argv)}"
            )


def _parse_entity(obj: Dict[str, Any]) -> Optional[_Entity]:
    record_type = obj.get("type")
    if record_type == "SOURCE_FILE":
        name = obj.get("sourceFile", {}).get("name")
        if not name:
            return None
        return _Entity(label=name, kind=_SOURCE_FILE_KIND)
    if record_type != "RULE":
        return None

    rule = obj.get("rule", {})
    label = rule.get("name")
    if not label:
        return None

    tags: List[str] = []
    imports: List[str] = []
    attr_labels: Dict[str, List[str]] = {}
    for attr in rule.get("attribute", []):
        name = attr.get("name")
        if name == "tags":
            tags = list(attr.get("stringListValue", []))
        elif name == "imports":
            imports = list(attr.get("stringListValue", []))
        elif name in _SUBTREE_FILE_ATTRS:
            values: List[str] = []
            if "stringListValue" in attr:
                values.extend(attr["stringListValue"])
            elif attr.get("stringValue"):
                values.append(attr["stringValue"])
            if values:
                attr_labels[name] = values

    return _Entity(
        label=label,
        kind=rule.get("ruleClass", ""),
        tags=tags,
        imports=imports,
        attr_labels=attr_labels,
    )


def _resolve_files(root: _Entity, entities: Dict[str, _Entity]) -> Set[str]:
    """Walk the file-carrying subgraph starting at a PyInfo root.

    Only `_ROOT_FILE_ATTRS` are read on `root`. Any rule reached below
    the root has all of `_SUBTREE_FILE_ATTRS` inspected. External labels
    (`@repo//...`) are skipped so third-party sources are never returned.
    """
    files: Set[str] = set()
    visited: Set[str] = set()

    def _visit(label: str) -> None:
        if label.startswith("@") or label in visited:
            return
        entity = entities.get(label)
        if entity is None:
            return
        if entity.kind == _SOURCE_FILE_KIND:
            files.add(_label_to_path(label))
            return
        visited.add(label)
        for attr in _SUBTREE_FILE_ATTRS:
            for child in entity.attr_labels.get(attr, []):
                _visit(child)

    for attr in _ROOT_FILE_ATTRS:
        for child in root.attr_labels.get(attr, []):
            _visit(child)

    return files


def _quote_query_label(label: str) -> str:
    escaped = label.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped + '"'


def _label_to_path(label: str) -> str:
    if not label.startswith("//"):
        return label
    if label.startswith("//:"):
        return label[3:]
    return label[2:].replace(":", "/")


def _label_package(label: str) -> str:
    if not label.startswith("//"):
        return ""
    package, _sep, _name = label[2:].partition(":")
    return package


def _cli() -> None:
    """Ad-hoc entry point for validating the resolver against a live repo.

    Not wired into any BUILD target; run with `python3 -m` from the repo
    root during development. Prints one JSON object per discovered target.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bazel", type=Path, default=Path("bazel"))
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--ignore-tag", action="append", default=[])
    parser.add_argument("scope", nargs="+")
    args = parser.parse_args()

    workspace = args.workspace or Path(
        os.environ.get("BUILD_WORKSPACE_DIRECTORY", os.getcwd())
    )
    targets = query_python_targets(
        scope=args.scope,
        bazel=args.bazel,
        workspace_dir=workspace,
        ignore_tags=args.ignore_tag,
    )
    for target in targets:
        print(
            json.dumps(
                {
                    "label": target.label,
                    "imports": list(target.imports),
                    "files": list(target.files),
                }
            )
        )


if __name__ == "__main__":
    _cli()
