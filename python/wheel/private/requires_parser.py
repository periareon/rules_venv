"""A tool for generating a list of requirements for a given `py_library` target."""

import argparse
import re
from pathlib import Path
from typing import Dict


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


def parse_constraints(constraints_file: Path) -> Dict[str, str]:
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
    # ```
    pattern = re.compile(r"^([\w\-_\.\d]+)\w?([\[\]!=<>\-\.\d+\w,]*)$")

    for line in constraints_file.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith(("--", "#")):
            continue
        match = pattern.match(text)
        if not match:
            continue

        # Match the name sanitization from req-compile
        # https://github.com/sputt/req-compile/blob/1.0.0rc24/private/utils.bzl#L3-L12
        name = match.group(1).replace("-", "_").replace(".", "_").lower()
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
        constraint = constraints.get(dep, "")
        requirements.append(f"{dep}{constraint}")

    args.output.write_text("\n".join(sorted(requirements)) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
