"""py_ruff_mode_flag"""

load("@bazel_skylib//rules:common_settings.bzl", "BuildSettingInfo")

def _py_ruff_mode_flag_impl(ctx):
    allowed_values = ctx.attr.values
    value = ctx.build_setting_value

    for mode in value:
        if mode not in allowed_values:
            fail("Error setting `{}`: invalid value `{}`. Allowed values are: {}".format(
                ctx.label,
                mode,
                allowed_values,
            ))

    return [
        BuildSettingInfo(value = value),
    ]

py_ruff_mode_flag = rule(
    implementation = _py_ruff_mode_flag_impl,
    build_setting = config.string_list(flag = True),
    attrs = {
        "scope": attr.string(
            doc = "The scope indicates where a flag can propagate to",
            default = "universal",
        ),
        "values": attr.string_list(
            doc = "The list of allowed values for this setting. An error is raised if any other value is given.",
        ),
    },
    doc = "A string list-typed build setting that can be set on the command line",
)
