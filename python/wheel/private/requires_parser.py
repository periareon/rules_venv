"""A tool for generating a list of requirements for a given `py_library` target."""

import argparse
import re
from pathlib import Path

# The name of a distribution, as PEP 508 defines it:
# https://peps.python.org/pep-0508/#names
_NAME_PATTERN = re.compile(r"^([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])$")


def normalize_name(name: str) -> str:
    """Normalize the name of a distribution so that its spellings compare equal.

    This is the normalization of PEP 503 with `_` for the separator instead of
    `-`, which is how `req-compile` sanitizes names into target names, so that
    names read from labels and from `pypi_name=` tags agree.
    https://github.com/sputt/req-compile/blob/1.0.0rc24/private/utils.bzl#L3-L12

    Args:
        name: The name of a distribution, however spelled.

    Returns:
        The normalized name.
    """
    return re.sub(r"[-_.]+", "_", name).lower()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="The output location for the requires file.",
    )
    parser.add_argument(
        "--constraints_file",
        type=Path,
        help="A file containing constraints data for detected requirements.",
    )
    parser.add_argument(
        "--dep",
        dest="deps",
        type=str,
        action="append",
        default=[],
        help="All external dependencies the package depends on.",
    )

    return parser.parse_args()


def parse_constraints(constraints_file: Path) -> dict[str, str]:
    """Parse a constraints (`requirements.in`) file into a map of package names to their constriants

    Args:
        constraints_file: A file containing package constraints. E.g. `requirements.in`.

    Returns:
        A mapping of package names to their semver constraints.
    """
    constraints = {}

    # A pattern to parse requirements. The two capture groups are the name of the constraints.
    # There is no reason to track packages without constraints since they'd have no impact
    # on requested requirements.
    #
    # Example matches:
    # ```
    # foo-pkg==1.0.0
    # foo_pkg!=1.0.0,!=2.0.0
    # foo.pkg[extra]
    # f00.pkg[extra]<=1.0.0
    # foo-pkg~=1.0
    # ```
    pattern = re.compile(r"^([\w\-_\.\d]+)\w?([\[\]!=<>~\-\.\d+\w,]*)$")

    for line in constraints_file.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith(("--", "#")):
            continue
        match = pattern.match(text)
        if not match:
            continue

        name = normalize_name(match.group(1))
        constraint = match.group(2).strip()
        constraints[name] = constraint

    return constraints


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    constraints = {}
    if args.constraints_file:
        constraints = parse_constraints(args.constraints_file)

    requirements = []

    for dep in args.deps:
        if not _NAME_PATTERN.match(dep):
            raise ValueError(
                f"`{dep}` is not the name of a distribution "
                "(https://peps.python.org/pep-0508/#names). A dependency of a wheel is "
                "named by its `pypi_name=` tag, or failing that by its label."
            )
        constraint = constraints.get(normalize_name(dep), "")
        requirements.append(f"{dep}{constraint}")

    args.output.write_text("\n".join(sorted(requirements)) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
