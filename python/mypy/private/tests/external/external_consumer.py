"""Read a package out of another repository, private names included.

`@mypy_external_example` is not under this workspace's root, so nothing
this workspace declares gives its modules their names -- the packages
enclosing them do, which is both what its own action publishes under and
what the import below resolves to. The two agreeing is the whole point:
the dependency arrives here as a cache with its sources pruned away, and
a name that did not agree would leave an empty module behind.

`_tidy` is the part that says so sharply. It is reachable only from the
published entry, since nothing standing in for a module can forward an
underscore name.
"""

import widgets.core
from widgets.core import label


def describe(text: str) -> str:
    """Label some text through the external package.

    Args:
        text: The text to label.

    Returns:
        The label.
    """
    return label(text)


def tidy(text: str) -> str:
    """Tidy some text through the external package's private helper.

    Args:
        text: The text to tidy.

    Returns:
        The tidied text.
    """
    # pylint: disable=protected-access
    return widgets.core._tidy(text)
