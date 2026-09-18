"""A package that is only ever imported by its own short name.

Code copied into a repository from elsewhere keeps the imports it was
written with, so it reaches its own submodules by the name it has when
it is installed rather than by where it now sits. `imports` on the
`py_library` gives it that name back. See `whole`, which is where the
spelling actually matters.
"""
