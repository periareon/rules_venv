# Examples

Each directory is a Bazel module of its own that depends on `rules_venv`
through `local_path_override`.

- [`binary_consumer`](./binary_consumer): consuming a `py_binary`.
- [`py_wasm_module`](./py_wasm_module): building Python into a WebAssembly
  module, and a consumer module calling it from a repository rule.
