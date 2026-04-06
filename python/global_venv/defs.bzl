"""# Global Venv

Bazel rules for generating usable [virtualenv][venv] from Bazel targets.

## Usage

A venv can be created by invoking the following command

```bash
bazel run @rules_venv//python/global_venv
```

From here a [venv][venv] will likely be available at `.venv` within your workspace that
can be activated for improved IDE support.

## Entrypoints

By default, `py_global_venv` auto-discovers `console_scripts` entrypoints from pip
packages (via `importlib.metadata`) and generates executable scripts in the venv's
`bin/` directory. This allows IDEs to find tools like `black` or `mypy` inside the venv.

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
