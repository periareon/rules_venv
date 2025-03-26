"""black dependencies"""

# buildifier: disable=unnamed-macro
def rules_black_dependencies():
    """Defines black dependencies"""
    pass

# buildifier: disable=unnamed-macro
def register_black_toolchains(register_toolchains = True):
    """Defines black dependencies"""
    if register_toolchains:
        native.register_toolchains(
            str(Label("//python/black/toolchain")),
        )
