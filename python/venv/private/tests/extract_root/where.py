"""Print the interpreter this process runs under."""

import sys


def main() -> None:
    """The main entrypoint."""
    print(sys.executable)


if __name__ == "__main__":
    main()
