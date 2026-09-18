"""A dependency published for its types that does not check clean itself.

This is what vendored code looks like: exempted from reporting precisely
because it has errors in it, and depended on for its types all the same.
Its action reaches it by import rather than naming its file, for two
reasons.

The first holds on every mypy, and is what this package asserts here:
naming a file resolves it without the import search, so the producer
never finds out whether the canonical name it published is one a consumer
can reach. Importing it is the same lookup the consumer will do, and a
name that does not resolve leaves the module out of the cache -- which
the consumer notices immediately, its own copy of the source having been
pruned in favour of that cache.

The second holds on the mypy versions that delete a module's cache when
they reported an error in it, which is every 1.x. Naming this file would
get the error reported to nobody, since the action publishing this cache
drops its diagnostics, and the cache deleted on the way out, leaving
nothing anywhere to read `describe` off. Followed imports are silenced,
so nothing is reported and nothing is deleted. See
`mypy_modules.analyzed`.
"""


def describe(name: str) -> str:
    """Render a name, correctly.

    Args:
        name: The name to render.

    Returns:
        The rendered name.
    """
    return f"<{name}>"


def miscounted() -> int:
    """Return something other than what it promises.

    The error this file exists to hold. Nothing reports it -- the target
    is tagged out of every checker -- but mypy still finds it, which on
    the versions that delete a cache over one is all it takes.

    Returns:
        A string, where the signature says otherwise.
    """
    return "not a number"
