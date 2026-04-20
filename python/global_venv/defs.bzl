"""# Global Venv

Bazel rules for generating usable [virtualenv][venv] from Bazel targets.

## Usage

A venv can be created by invoking the following command

```bash
bazel run @rules_venv//python/global_venv
```

From here a [venv][venv] will likely be available at `.venv` within your workspace that
can be activated for improved IDE support.

## Pyright / Pylance

By default, a `bazel-pyrightconfig.json` is generated with `extraPaths` pointing to
each Bazel output directory that contains generated Python sources. To use it, add
an `extends` field to your `pyrightconfig.json`:

```json
{
    "extends": "bazel-pyrightconfig.json"
}
```

**Important:** Do not define `extraPaths` in your own `pyrightconfig.json`. Pyright's
`extends` replaces array fields rather than merging them, so any `extraPaths` in the
child config will override the generated values.

## Ruff / isort

Ruff classifies imports as first-party by checking whether the imported module can be
resolved under its `src` directories. Generated sources (`.pyi` stubs, `.so` extensions)
only exist under `bazel-out`, so ruff needs those directories in `src`:

```toml
# .ruff.toml
src = [".", "bazel-out/k8-*/bin"]
```

For standalone isort:

```ini
# .isort.cfg
[isort]
src_paths = .,bazel-out/k8-*/bin
```

The glob `k8-*` covers all Bazel configurations (`k8-fastbuild`, `k8-opt`, `k8-dbg`).

## Entrypoints

By default, `py_global_venv` auto-discovers `console_scripts` entrypoints from pip
packages (via `importlib.metadata`) and generates executable scripts in the venv's
`bin/` directory. Pre-built binaries shipped via wheel data scripts (e.g. `ruff`) are
also symlinked into the venv. This allows IDEs to find tools like `black`, `ruff`, or
`mypy` inside the venv.

Additional entrypoints can be specified manually:

```python
py_global_venv(
    name = "global_venv",
    entrypoints = {
        "my_tool": "my.module:cli",
    },
)
```

Auto-discovery can be disabled with `gen_entrypoints = False`.

[venv]: https://docs.python.org/3/library/venv.html

"""

load(
    ":py_global_venv.bzl",
    _py_global_venv = "py_global_venv",
)
load(
    ":py_global_venv_aspect.bzl",
    _py_global_venv_aspect = "py_global_venv_aspect",
)

py_global_venv_aspect = _py_global_venv_aspect
py_global_venv = _py_global_venv
