"""rules_mypy dependencies"""

# buildifier: disable=unnamed-macro
def rules_mypy_dependencies():
    """Defines mypy dependencies"""
    pass

# buildifier: disable=unnamed-macro
def register_mypy_toolchains(register_toolchains = True):
    """Defines pytest dependencies"""
    if register_toolchains:
        native.register_toolchains(
            str(Label("//python/mypy/toolchain")),
        )
