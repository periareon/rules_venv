"""Copy the built module into the consumer module, standing in for publishing it."""

import os
import platform
import shutil
from pathlib import Path

from python.runfiles import Runfiles


def main() -> None:
    """The main entrypoint."""
    runfiles = Runfiles.Create()
    assert runfiles
    # TODO: https://github.com/periareon/rules_venv/issues/37
    source_repo = "" if platform.system() == "Windows" else None
    module = runfiles.Rlocation(os.environ["GREETER_WASM"], source_repo)
    assert module
    destination = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"]) / "consumer" / "greeter.wasm"
    shutil.copyfile(module, destination)
    print(f"published {destination}")


if __name__ == "__main__":
    main()
