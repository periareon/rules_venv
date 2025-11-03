"""A rule that creates a directory with nested files."""

def _directory_maker_impl(ctx):
    # Declare the output directory
    output_dir = ctx.actions.declare_directory(ctx.attr.name + "_dir")

    # Use the Python script to generate the directory structure
    args = ctx.actions.args()
    args.add("--output", output_dir.path)
    args.add("--content", ctx.attr.content)

    # Run the script to create the directory
    ctx.actions.run(
        mnemonic = "MakeDirectory",
        executable = ctx.executable._script,
        arguments = [args],
        outputs = [output_dir],
    )

    return [DefaultInfo(
        files = depset([output_dir]),
        runfiles = ctx.runfiles(files = [output_dir]),
    )]

directory_maker = rule(
    doc = "A rule that creates a directory with nested files for testing.",
    implementation = _directory_maker_impl,
    attrs = {
        "content": attr.string(
            doc = "The content to write to the nested data.txt file.",
            mandatory = True,
        ),
        "_script": attr.label(
            doc = "The Python script that generates the directory structure.",
            default = Label("//python/venv/private/tests/data_dir/private:directory_maker"),
            cfg = "exec",
            executable = True,
        ),
    },
)
