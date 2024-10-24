<!-- Generated with Stardoc: http://skydoc.bazel.build -->

# rules_venv

## Overview

This repository implements Bazel rules for Python and is designed to be a drop-in replacement for the existing
[rules_python](https://github.com/bazelbuild/rules_python) where uses of `@rules_python//python:defs.bzl` can
be replaced with `@rules_venv//python:defs.bzl`.

### Improvements over `rules_python`

While `rules_python` has fantastic toolchain infrastructure which this repo relies on, `rules_python` ultimately
suffers from a few issues which this repo aims to solve:

1. Use of `PYTHONPATH` to construct the python environment leads to operating system limitations.

    Some details on `MAX_ARG_STRLEN` and `ARG_MAX` can be found here: https://unix.stackexchange.com/a/120842

2. Slow startup on windows systems that do not support symlinks.

    `rules_python` creates zipapps on systems that do not support runfiles. For large projects, this can lead to
    large (~500MB+) zip files being constantly compressed and uncompressed to run simple actions which is a lot
    more expensive than systems which support runfiles.

## Setup

### WORKSPACE.bazel

```starlark
load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# See releases for urls and checksums
http_archive(
    name = "rules_venv",
    sha256 = "{sha256}",
    urls = ["https://github.com/periareon/rules_venv/releases/download/{version}/rules_venv-v{version}.tar.gz"],
)

load("@rules_venv//venv:repositories.bzl", "venv_register_toolchains", "rules_venv_dependencies")

rules_venv_dependencies()

venv_register_toolchains()

load("@rules_venv//python/venv:repositories_transitive.bzl", "rules_venv_transitive_deps")

rules_venv_transitive_deps()
```

### bzlmod

```starlark
bazel_dep(name = "rules_venv", version = "{version}")
```

## `py_venv_common`

An experimental API for creating python executables within user author rules.

- [create_dep_info](#create_dep_info)
- [create_py_info](#create_py_info)
- [create_python_zip_file](#create_python_zip_file)
- [create_runfiles_collection](#create_runfiles_collection)
- [create_venv_attrs](#create_venv_attrs)
- [create_venv_entrypoint](#create_venv_entrypoint)
- [get_toolchain](#get_toolchain)

## Rules

- [py_venv_binary](#py_venv_binary)
- [py_venv_library](#py_venv_library)
- [py_venv_test](#py_venv_test)
- [py_venv_toolchain](#py_venv_toolchain)

---
---

<a id="py_venv_binary"></a>

## py_venv_binary

<pre>
py_venv_binary(<a href="#py_venv_binary-name">name</a>, <a href="#py_venv_binary-deps">deps</a>, <a href="#py_venv_binary-srcs">srcs</a>, <a href="#py_venv_binary-data">data</a>, <a href="#py_venv_binary-env">env</a>, <a href="#py_venv_binary-imports">imports</a>, <a href="#py_venv_binary-main">main</a>)
</pre>

A `py_venv_binary` is an executable Python program consisting of a collection of
`.py` source files (possibly belonging to other `py_library` rules), a `*.runfiles`
directory tree containing all the code and data needed by the program at run-time,
and a stub script that starts up the program with the correct initial environment
and data.

```python
load("@rules_venv//python/venv:defs.bzl", "py_venv_binary")

py_venv_binary(
    name = "foo",
    srcs = ["foo.py"],
    data = [":transform"],  # a cc_binary which we invoke at run time
    deps = [
        ":bar",  # a py_library
    ],
)
```

**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="py_venv_binary-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |
| <a id="py_venv_binary-deps"></a>deps |  Other python targets to link to the current target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_binary-srcs"></a>srcs |  The list of source (.py) files that are processed to create the target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_binary-data"></a>data |  Files needed by this rule at runtime. May list file or rule targets. Generally allows any target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_binary-env"></a>env |  Dictionary of strings; values are subject to `$(location)` and "Make variable" substitution.   | <a href="https://bazel.build/rules/lib/dict">Dictionary: String -> String</a> | optional |  `{}`  |
| <a id="py_venv_binary-imports"></a>imports |  List of import directories to be added to the `PYTHONPATH`.   | List of strings | optional |  `[]`  |
| <a id="py_venv_binary-main"></a>main |  The name of the source file that is the main entry point of the application. This file must also be listed in `srcs`. If left unspecified, `name` is used instead. If `name` does not match any filename in `srcs`, `main` must be specified.   | <a href="https://bazel.build/concepts/labels">Label</a> | optional |  `None`  |


<a id="py_venv_library"></a>

## py_venv_library

<pre>
py_venv_library(<a href="#py_venv_library-name">name</a>, <a href="#py_venv_library-deps">deps</a>, <a href="#py_venv_library-srcs">srcs</a>, <a href="#py_venv_library-data">data</a>, <a href="#py_venv_library-imports">imports</a>)
</pre>

A library of Python code that can be depended upon.

**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="py_venv_library-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |
| <a id="py_venv_library-deps"></a>deps |  Other python targets to link to the current target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_library-srcs"></a>srcs |  The list of source (.py) files that are processed to create the target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_library-data"></a>data |  Files needed by this rule at runtime. May list file or rule targets. Generally allows any target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_library-imports"></a>imports |  List of import directories to be added to the `PYTHONPATH`.   | List of strings | optional |  `[]`  |


<a id="py_venv_test"></a>

## py_venv_test

<pre>
py_venv_test(<a href="#py_venv_test-name">name</a>, <a href="#py_venv_test-deps">deps</a>, <a href="#py_venv_test-srcs">srcs</a>, <a href="#py_venv_test-data">data</a>, <a href="#py_venv_test-env">env</a>, <a href="#py_venv_test-env_inherit">env_inherit</a>, <a href="#py_venv_test-imports">imports</a>, <a href="#py_venv_test-main">main</a>)
</pre>

A `py_venv_test` rule compiles a test. A test is a binary wrapper around some test code.

**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="py_venv_test-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |
| <a id="py_venv_test-deps"></a>deps |  Other python targets to link to the current target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_test-srcs"></a>srcs |  The list of source (.py) files that are processed to create the target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_test-data"></a>data |  Files needed by this rule at runtime. May list file or rule targets. Generally allows any target.   | <a href="https://bazel.build/concepts/labels">List of labels</a> | optional |  `[]`  |
| <a id="py_venv_test-env"></a>env |  Dictionary of strings; values are subject to `$(location)` and "Make variable" substitution.   | <a href="https://bazel.build/rules/lib/dict">Dictionary: String -> String</a> | optional |  `{}`  |
| <a id="py_venv_test-env_inherit"></a>env_inherit |  Specifies additional environment variables to inherit from the external environment when the test is executed by `bazel test`.   | List of strings | optional |  `[]`  |
| <a id="py_venv_test-imports"></a>imports |  List of import directories to be added to the `PYTHONPATH`.   | List of strings | optional |  `[]`  |
| <a id="py_venv_test-main"></a>main |  The name of the source file that is the main entry point of the application. This file must also be listed in `srcs`. If left unspecified, `name` is used instead. If `name` does not match any filename in `srcs`, `main` must be specified.   | <a href="https://bazel.build/concepts/labels">Label</a> | optional |  `None`  |


<a id="py_venv_toolchain"></a>

## py_venv_toolchain

<pre>
py_venv_toolchain(<a href="#py_venv_toolchain-name">name</a>, <a href="#py_venv_toolchain-zipapp_shebang">zipapp_shebang</a>)
</pre>

Declare a toolchain for `rules_venv` rules.

**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="py_venv_toolchain-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |
| <a id="py_venv_toolchain-zipapp_shebang"></a>zipapp_shebang |  The shebang to use when creating zipapps (`OutputGroupInfo.python_zip_file`).   | String | optional |  `""`  |


<a id="py_venv_common.create_dep_info"></a>

## py_venv_common.create_dep_info

<pre>
py_venv_common.create_dep_info(<a href="#py_venv_common.create_dep_info-ctx">ctx</a>, <a href="#py_venv_common.create_dep_info-deps">deps</a>)
</pre>

Construct dependency info required for building `PyInfo`

**PARAMETERS**


| Name  | Description | Default Value |
| :------------- | :------------- | :------------- |
| <a id="py_venv_common.create_dep_info-ctx"></a>ctx |  The rule's context object.   |  none |
| <a id="py_venv_common.create_dep_info-deps"></a>deps |  A list of python dependency targets   |  none |

**RETURNS**

struct: Dependency info.


<a id="py_venv_common.create_py_info"></a>

## py_venv_common.create_py_info

<pre>
py_venv_common.create_py_info(<a href="#py_venv_common.create_py_info-ctx">ctx</a>, <a href="#py_venv_common.create_py_info-imports">imports</a>, <a href="#py_venv_common.create_py_info-srcs">srcs</a>, <a href="#py_venv_common.create_py_info-dep_info">dep_info</a>)
</pre>

Construct a `PyInfo` provider

**PARAMETERS**


| Name  | Description | Default Value |
| :------------- | :------------- | :------------- |
| <a id="py_venv_common.create_py_info-ctx"></a>ctx |  The rule's context object.   |  none |
| <a id="py_venv_common.create_py_info-imports"></a>imports |  The raw `imports` attribute.   |  none |
| <a id="py_venv_common.create_py_info-srcs"></a>srcs |  A list of python (`.py`) source files.   |  none |
| <a id="py_venv_common.create_py_info-dep_info"></a>dep_info |  Dependency info from the current target.   |  `None` |

**RETURNS**

PyInfo: A `PyInfo` provider.


<a id="py_venv_common.create_python_zip_file"></a>

## py_venv_common.create_python_zip_file

<pre>
py_venv_common.create_python_zip_file(<a href="#py_venv_common.create_python_zip_file-ctx">ctx</a>, <a href="#py_venv_common.create_python_zip_file-venv_toolchain">venv_toolchain</a>, <a href="#py_venv_common.create_python_zip_file-py_info">py_info</a>, <a href="#py_venv_common.create_python_zip_file-main">main</a>, <a href="#py_venv_common.create_python_zip_file-runfiles">runfiles</a>, <a href="#py_venv_common.create_python_zip_file-py_toolchain">py_toolchain</a>,
                                      <a href="#py_venv_common.create_python_zip_file-name">name</a>)
</pre>

Create a zipapp.

**PARAMETERS**


| Name  | Description | Default Value |
| :------------- | :------------- | :------------- |
| <a id="py_venv_common.create_python_zip_file-ctx"></a>ctx |  The rule's context object.   |  none |
| <a id="py_venv_common.create_python_zip_file-venv_toolchain"></a>venv_toolchain |  A `py_venv_toolchain` toolchain.   |  none |
| <a id="py_venv_common.create_python_zip_file-py_info"></a>py_info |  The `PyInfo` provider for the current target.   |  none |
| <a id="py_venv_common.create_python_zip_file-main"></a>main |  The main python entrypoint.   |  none |
| <a id="py_venv_common.create_python_zip_file-runfiles"></a>runfiles |  Runfiles associated with the executable.   |  none |
| <a id="py_venv_common.create_python_zip_file-py_toolchain"></a>py_toolchain |  A `py_toolchain` toolchain. If one is not provided one will be acquired via `py_venv_toolchain`.   |  `None` |
| <a id="py_venv_common.create_python_zip_file-name"></a>name |  An alternate name to use in the output instead of `ctx.label.name`.   |  `None` |

**RETURNS**

File: The generated zip file.


<a id="py_venv_common.create_runfiles_collection"></a>

## py_venv_common.create_runfiles_collection

<pre>
py_venv_common.create_runfiles_collection(<a href="#py_venv_common.create_runfiles_collection-ctx">ctx</a>, <a href="#py_venv_common.create_runfiles_collection-venv_toolchain">venv_toolchain</a>, <a href="#py_venv_common.create_runfiles_collection-py_toolchain">py_toolchain</a>, <a href="#py_venv_common.create_runfiles_collection-runfiles">runfiles</a>,
                                          <a href="#py_venv_common.create_runfiles_collection-exclude_files">exclude_files</a>, <a href="#py_venv_common.create_runfiles_collection-name">name</a>, <a href="#py_venv_common.create_runfiles_collection-use_zip">use_zip</a>)
</pre>

Generate a runfiles directory

This functionality exists due to the lack of native support for generating
runfiles in an action. For details see: https://github.com/bazelbuild/bazel/issues/15486


**PARAMETERS**


| Name  | Description | Default Value |
| :------------- | :------------- | :------------- |
| <a id="py_venv_common.create_runfiles_collection-ctx"></a>ctx |  The rule's context object.   |  none |
| <a id="py_venv_common.create_runfiles_collection-venv_toolchain"></a>venv_toolchain |  A `py_venv_toolchain` toolchain.   |  none |
| <a id="py_venv_common.create_runfiles_collection-py_toolchain"></a>py_toolchain |  A `py_toolchain` toolchain.   |  none |
| <a id="py_venv_common.create_runfiles_collection-runfiles"></a>runfiles |  The runfiles to render into a directory   |  none |
| <a id="py_venv_common.create_runfiles_collection-exclude_files"></a>exclude_files |  A collection of files to exclude from the collection despite them appearing in `runfiles`.   |  `depset([])` |
| <a id="py_venv_common.create_runfiles_collection-name"></a>name |  An alternate name to use in the output instead of `ctx.label.name`.   |  `None` |
| <a id="py_venv_common.create_runfiles_collection-use_zip"></a>use_zip |  If True, a zip file will be generated instead of a json manifest.   |  `False` |

**RETURNS**

Tuple[File, Runfiles]: The generated runfiles collection and associated runfiles.


<a id="py_venv_common.create_venv_attrs"></a>

## py_venv_common.create_venv_attrs

<pre>
py_venv_common.create_venv_attrs()
</pre>





<a id="py_venv_common.create_venv_entrypoint"></a>

## py_venv_common.create_venv_entrypoint

<pre>
py_venv_common.create_venv_entrypoint(<a href="#py_venv_common.create_venv_entrypoint-ctx">ctx</a>, <a href="#py_venv_common.create_venv_entrypoint-venv_toolchain">venv_toolchain</a>, <a href="#py_venv_common.create_venv_entrypoint-py_info">py_info</a>, <a href="#py_venv_common.create_venv_entrypoint-main">main</a>, <a href="#py_venv_common.create_venv_entrypoint-runfiles">runfiles</a>, <a href="#py_venv_common.create_venv_entrypoint-py_toolchain">py_toolchain</a>,
                                      <a href="#py_venv_common.create_venv_entrypoint-name">name</a>, <a href="#py_venv_common.create_venv_entrypoint-use_runfiles_in_entrypoint">use_runfiles_in_entrypoint</a>, <a href="#py_venv_common.create_venv_entrypoint-force_runfiles">force_runfiles</a>)
</pre>

Create an executable which constructs a python venv and subprocesses a given entrypoint.

**PARAMETERS**


| Name  | Description | Default Value |
| :------------- | :------------- | :------------- |
| <a id="py_venv_common.create_venv_entrypoint-ctx"></a>ctx |  The rule's context object.   |  none |
| <a id="py_venv_common.create_venv_entrypoint-venv_toolchain"></a>venv_toolchain |  A `py_venv_toolchain` toolchain.   |  none |
| <a id="py_venv_common.create_venv_entrypoint-py_info"></a>py_info |  The `PyInfo` provider for the current target.   |  none |
| <a id="py_venv_common.create_venv_entrypoint-main"></a>main |  The main python entrypoint.   |  none |
| <a id="py_venv_common.create_venv_entrypoint-runfiles"></a>runfiles |  Runfiles associated with the executable.   |  none |
| <a id="py_venv_common.create_venv_entrypoint-py_toolchain"></a>py_toolchain |  A `py_toolchain` toolchain. If one is not provided one will be acquired via `py_venv_toolchain`.   |  `None` |
| <a id="py_venv_common.create_venv_entrypoint-name"></a>name |  An alternate name to use in the output instead of `ctx.label.name`.   |  `None` |
| <a id="py_venv_common.create_venv_entrypoint-use_runfiles_in_entrypoint"></a>use_runfiles_in_entrypoint |  If true, an entrypoint will be created that relies on runfiles.   |  `True` |
| <a id="py_venv_common.create_venv_entrypoint-force_runfiles"></a>force_runfiles |  If True, a rendered runfiles directory will be used over builtin runfiles where `RUNFILES_DIR` would be provided.   |  `False` |

**RETURNS**

Tuple[File, Runfiles]: The generated entrypoint and associated runfiles.


<a id="py_venv_common.get_toolchain"></a>

## py_venv_common.get_toolchain

<pre>
py_venv_common.get_toolchain(<a href="#py_venv_common.get_toolchain-ctx">ctx</a>, <a href="#py_venv_common.get_toolchain-cfg">cfg</a>)
</pre>



**PARAMETERS**


| Name  | Description | Default Value |
| :------------- | :------------- | :------------- |
| <a id="py_venv_common.get_toolchain-ctx"></a>ctx |  <p align="center"> - </p>   |  none |
| <a id="py_venv_common.get_toolchain-cfg"></a>cfg |  <p align="center"> - </p>   |  `"target"` |


<a id="py_global_venv_aspect"></a>

## py_global_venv_aspect

<pre>
py_global_venv_aspect(<a href="#py_global_venv_aspect-name">name</a>)
</pre>

An aspect for generating metadata required to include Python targets in a global venv.

**ASPECT ATTRIBUTES**



**ATTRIBUTES**


| Name  | Description | Type | Mandatory | Default |
| :------------- | :------------- | :------------- | :------------- | :------------- |
| <a id="py_global_venv_aspect-name"></a>name |  A unique name for this target.   | <a href="https://bazel.build/concepts/labels#target-names">Name</a> | required |  |


