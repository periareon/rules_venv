"""Rules for creating python packages"""

load("@rules_python//python:defs.bzl", "PyInfo")

def _py_zipapp_impl(ctx):
    """The implementation of the `py_zipapp` rule.

    Args:
        ctx (ctx): The rule's context object

    Returns:
        list: A list of providers
    """
    bin = ctx.attr.bin

    # Extract the zip file
    python_zip_file = bin[OutputGroupInfo].python_zip_file.to_list()
    if len(python_zip_file) > 1:
        fail("Unexpected number of files in `python_zip_file` output group")
    zip_file = python_zip_file[0]

    args = ctx.actions.args()
    args.add("--python_zip_file", zip_file)
    args.add("--run_under_runfiles", ctx.attr.run_under_runfiles)

    # The shebang is nearly meaningless but it helps invoke the bazel wrapper
    # generated for the py_binary which also contains it's own shebang and hard
    # coded information about the python interpreter from the toolchain.
    args.add("--shebang", ctx.attr.shebang)

    # Explicitly pass the template file to render as the zipapp entrypoint
    args.add("--zipapp_main_template", ctx.file._pyz_main_template)

    # Define the well named `pyz` file per PEP-0441
    # https://www.python.org/dev/peps/pep-0441/
    zipapp = ctx.actions.declare_file(ctx.label.name + ".pyz")
    args.add("--output", zipapp)

    ctx.actions.run(
        executable = ctx.executable._pyz_maker,
        arguments = [args],
        inputs = [zip_file, ctx.file._pyz_main_template],
        outputs = [zipapp],
        mnemonic = "PyZipapp",
        progress_message = "Creating python zipapp for {}".format(ctx.label),
    )

    return [DefaultInfo(
        files = depset([zipapp]),
        executable = zipapp,
    )]

py_zipapp = rule(
    implementation = _py_zipapp_impl,
    doc = (
        "This rule builds a python [zipapp](https://docs.python.org/3/library/zipapp.html) " +
        "from a [py_binary](https://docs.bazel.build/versions/master/be/python.html#py_binary)."
    ),
    attrs = {
        "bin": attr.label(
            doc = "The py_binary to convert into a zipapp.",
            cfg = "target",
            executable = True,
            providers = [PyInfo],
        ),
        "run_under_runfiles": attr.int(
            doc = (
                "Whether or not the zipapp should run under runfiles. This " +
                "means the process will run with the runfiles directory as " +
                "`cwd`. `-1` will leave it up to the `RUN_UNDER_RUNFILES` " +
                "environment variable at runtime, `0` will force disable " +
                "this behavior, and `1` will force enable it"
            ),
            values = [-1, 0, 1],
            default = -1,
        ),
        "shebang": attr.string(
            doc = "The shebang to use for the zipapp entrypoint.",
            default = "/usr/bin/env python3",
        ),
        "_pyz_main_template": attr.label(
            doc = "A template python main file.",
            allow_single_file = True,
            default = Label("//python/zipapp/private:pyz_main_template.py"),
        ),
        "_pyz_maker": attr.label(
            doc = "A tool for building python zipapps.",
            cfg = "exec",
            executable = True,
            default = Label("//python/zipapp/private:pyz_maker"),
        ),
    },
    executable = True,
)
