"""A rule for building a target for an explicit target platform."""

_PLATFORMS = "//command_line_option:platforms"

def _platform_transition_impl(_settings, attr):
    return {_PLATFORMS: str(attr.platform)}

_platform_transition = transition(
    implementation = _platform_transition_impl,
    inputs = [],
    outputs = [_PLATFORMS],
)

def _platform_build_impl(ctx):
    return [DefaultInfo(
        files = ctx.attr.target[0][DefaultInfo].files,
    )]

platform_build = rule(
    doc = """\
Rebuild `target` for the given target platform and forward its default outputs.

Executables and zipapps may be produced for a platform other than the one
building them. Every action behind them must therefore run with tools for the
execution platform, regardless of what the target platform is. Building this
target on a host whose operating system differs from `platform` checks exactly
that.
""",
    implementation = _platform_build_impl,
    attrs = {
        "platform": attr.label(
            doc = "The platform to build `target` for.",
            mandatory = True,
            providers = [platform_common.PlatformInfo],
        ),
        "target": attr.label(
            doc = "The target to build.",
            mandatory = True,
            cfg = _platform_transition,
        ),
    },
)
