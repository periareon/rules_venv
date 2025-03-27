"""A simple script to test pylint behavior against."""

import argparse

from greeting import greeting  # type: ignore

from python.pylint.private.tests.imports.fibonacci import fibonacci_of


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--fibonacci", type=int, help="The Nth Fibonacci sequence to compute."
    )
    parser.add_argument("--greeting", type=str, help="The name of the entity to greet.")

    args = parser.parse_args()
    if not args.fibonacci and not args.greeting:
        parser.error("Either `--fibonacci` or `--greeting` must be passed.")

    return args


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    if args.fibonacci:
        print([fibonacci_of(n) for n in range(args.num)])

    if args.greeting:
        print(greeting(args.greeting))


if __name__ == "__main__":
    main()
