"""venv dependencies"""

load("@rules_python//python:repositories.bzl", "py_repositories")

# buildifier: disable=unnamed-macro
def rules_venv_transitive_deps():
    """Defines venv transitive dependencies"""

    py_repositories()
