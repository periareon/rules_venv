"""A test runner for ensuring aspect created entrypoints produce working python environments."""

import argparse
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# isort: off


class ActionTest(unittest.TestCase):
    """Test cases to confirm the python environment is setup correctly for actions."""

    def test_greetings(self) -> None:
        """Test that an aspect target's python libraries are importable."""
        # pylint: disable-next=import-outside-toplevel,no-name-in-module
        from python.venv.private.tests.common_api.aspect_dep.greeting import (  # type: ignore
            greeting as aspect_greeting,
        )

        # pylint: disable-next=import-outside-toplevel,no-name-in-module
        from python.venv.private.tests.common_api.user_dep.greeting import (  # type: ignore
            greeting as user_greeting,
        )

        self.assertEqual(aspect_greeting("World"), user_greeting("World"))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output", type=Path, required=True, help="The path to the output file."
    )

    return parser.parse_args()


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    stream = io.StringIO()

    with redirect_stderr(stream), redirect_stdout(stream):
        # Run unit tests ensuring the python environment is configured correcty.
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(ActionTest)
        runner = unittest.TextTestRunner()
        result = runner.run(suite)

    if not result.wasSuccessful():
        print(stream.getvalue(), file=sys.stderr)
        sys.exit(1)

    # Touch the output file to indicate the action succeeded.
    args.output.write_text("La-Li-Lu-Le-Lo", encoding="utf-8")


if __name__ == "__main__":
    main()
