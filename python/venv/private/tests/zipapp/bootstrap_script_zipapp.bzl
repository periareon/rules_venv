"""A rule for building a zipapp under `bootstrap_impl=script`."""

_BOOTSTRAP_IMPL = "@rules_python//python/config_settings:bootstrap_impl"

def _bootstrap_script_transition_impl(_settings, _attr):
    return {_BOOTSTRAP_IMPL: "script"}

_bootstrap_script_transition = transition(
    implementation = _bootstrap_script_transition_impl,
    inputs = [],
    outputs = [_BOOTSTRAP_IMPL],
)

def _bootstrap_script_zipapp_impl(ctx):
    return [DefaultInfo(
        files = depset([ctx.file.zipapp]),
    )]

bootstrap_script_zipapp = rule(
    doc = """\
Rebuild a `py_venv_zipapp` with `bootstrap_impl=script`, the mode in which
`rules_python` stages a build time venv into a `py_binary`'s runfiles. The
venv's interpreter is a symlink whose target only resolves within a runfiles
directory, so it must never be copied into a zipapp.

The transition is attached here rather than to any consumer so that the flag
travels with the artifact and any rule or test may consume the result.
""",
    implementation = _bootstrap_script_zipapp_impl,
    attrs = {
        "zipapp": attr.label(
            doc = "A `py_venv_zipapp` target.",
            mandatory = True,
            allow_single_file = True,
            cfg = _bootstrap_script_transition,
        ),
    },
)
