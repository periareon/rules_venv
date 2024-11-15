"""Test utilities"""

def _template_variable_test_toolchain_impl(_ctx):
    return [
        platform_common.ToolchainInfo(),
        platform_common.TemplateVariableInfo({
            "LA_LI_LU_LE_LO": "Hello World!",
        }),
    ]

template_variable_test_toolchain = rule(
    doc = "A toolchainf or testing template variable expansions.",
    implementation = _template_variable_test_toolchain_impl,
)
