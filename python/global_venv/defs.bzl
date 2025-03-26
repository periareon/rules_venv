"""# Global Venv

Bazel rules for generating usable [virtualenv][venv] from Bazel targets.

## Usage

A venv can be created by invoking the following command

```bash
bazel run @rules_venv//python/global_venv
```

From here a [venv][venv] will likely be available at `.venv` within your workspace that
can be activated for improved IDE support.

[venv]: https://docs.python.org/3/library/venv.html

"""

load(
    "//python/global_venv/private:global_venv.bzl",
    _py_global_venv_aspect = "py_global_venv_aspect",
)

py_global_venv_aspect = _py_global_venv_aspect
