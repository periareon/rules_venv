# py_wasm_module

Two modules: this one builds Python into a WebAssembly module with
`py_wasm_module` and publishes it; `consumer/`, a module of its own, calls it
from a Bazel repository rule through `repository_ctx.execute_wasm` (Bazel 9.3
or newer, behind the flag in `.bazelrc`). The consumer depends on neither
rules_venv nor Python: the rule has nothing specific to Bazel, and
`execute_wasm` consumes the calling convention every `py_wasm_module` has.

- `greeter.py` is the Python; `BUILD.bazel` builds it into `greeter.wasm`.
- `bazel run //:publish` copies the module into `consumer/`, standing in for
  publishing it where a repository rule would download it from.
- `consumer/greeting.bzl` calls the module's `greet` export and keeps the
  answer as `@greeting//:greeting.txt`, which `@consumer//:greeting` copies out
  and `//:greeting_test` checks.

The consumer is a dependency of this module (`local_path_override` into
`consumer/`, which `.bazelignore` keeps out of this module's own packages), and
Bazel fetches a repository only when a target needs it, so publishing comes
first and the test after:

```shell
bazel run //:publish
bazel test //...
```
