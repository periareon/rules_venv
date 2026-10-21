"""A repository rule that calls `greeter.wasm` with `repository_ctx.execute_wasm`.

`execute_wasm` instantiates a module that imports nothing, places the input
with the module's `allocate` and calls an export of the signature
`(input, input_len, out_ptr, out_len) -> code`: the calling convention every
`py_wasm_module` has, so the module serves unchanged. Here the module is a file
of this workspace, published by the module that built it; a rule meant for use
would fetch a released one with `repository_ctx.download` instead.
"""

def _greeting_impl(repository_ctx):
    path = repository_ctx.path(Label("//:greeter.wasm"))
    if not path.exists:
        fail("{} is not published yet; `bazel run //:publish` in the module that builds it.".format(path))
    repository_ctx.watch(path)
    module = repository_ctx.load_wasm(path)
    result = repository_ctx.execute_wasm(
        module,
        "greet",
        input = "rules_venv",
        memory_limit = 256 * 1024 * 1024,
    )
    if result.return_code != 0:
        # On an exception the output holds the Python traceback.
        fail("greet failed with code {}:\n{}{}".format(result.return_code, result.output, result.error_message))
    repository_ctx.file("BUILD.bazel", 'exports_files(["greeting.txt"])\n')
    repository_ctx.file("greeting.txt", result.output)

_greeting = repository_rule(
    doc = "Calls `greet` in `//:greeter.wasm` and keeps its output as `greeting.txt`.",
    implementation = _greeting_impl,
)

def _greeting_extension_impl(_module_ctx):
    _greeting(name = "greeting")

greeting = module_extension(implementation = _greeting_extension_impl)
