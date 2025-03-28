"""rules_isort dependencies"""

# buildifier: disable=unnamed-macro
def rules_isort_dependencies():
    """Defines isort dependencies"""
    pass

# buildifier: disable=unnamed-macro
def isort_register_toolchains(register_toolchains = True):
    """Defines isort dependencies"""
    if register_toolchains:
        native.register_toolchains(
            str(Label("//python/isort/toolchain")),
        )
