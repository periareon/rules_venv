"""Rules that consume python_zip_file"""

def _python_zip_file_consumer_impl(ctx):
    py_toolchain = ctx.toolchains["@rules_python//python:toolchain_type"]
    py_runtime = py_toolchain.py3_runtime
    interpreter = None
    if py_runtime.interpreter:
        interpreter = py_runtime.interpreter

    if not interpreter:
        fail("Unable to locate interpreter from py_toolchain: {}".format(py_toolchain))

    output = ctx.actions.declare_file("{}.txt".format(ctx.label.name))

    args = ctx.actions.args()
    args.add(ctx.file.zip_file)
    args.add("--output", output)

    ctx.actions.run(
        mnemonic = "PythonZipFileConsumer",
        executable = interpreter,
        arguments = [args],
        outputs = [output],
        inputs = [ctx.file.zip_file],
        tools = py_runtime.files,
    )

    return [DefaultInfo(
        files = depset([output]),
    )]

python_zip_file_consumer = rule(
    doc = "A rule for invoking `python_zip_file` files from `py_venv_bianry` targets..",
    implementation = _python_zip_file_consumer_impl,
    attrs = {
        "zip_file": attr.label(
            doc = "A zipapp extracted from `python_zip_file`.",
            mandatory = True,
            allow_single_file = True,
        ),
    },
    toolchains = ["@rules_python//python:toolchain_type"],
)
