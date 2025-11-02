"""A tool which runs scie science to prefetch sufficient repository info such that a cache can be recreated in an action."""

import argparse
import base64
import binascii
import json
import logging
import os
import platform
import subprocess
import tempfile
from enum import IntEnum
from pathlib import Path
from typing import Any, NamedTuple

from python.runfiles import Runfiles

PYTHON_VERSIONS = (
    "3.10",
    "3.11",
    "3.12",
    "3.13",
    "3.14",
    "3.9",
)

PROVIDERS = [
    # TODO: Add support in the distant future.
    # "PyPy",
    "PythonBuildStandalone",
]


class LibcPreference(IntEnum):
    """Preference order for libc/ABI variants (higher is more preferred)."""

    MUSL = 0  # Fallback
    GNUEABI = 1  # Soft-float ABI for ARM
    GNU = 2  # Standard gnu libc (preferred for most platforms)
    GNUEABIHF = 3  # Hard-float ABI for ARM (most preferred)


class PlatformInfo(NamedTuple):
    """Platform identification and preference."""

    platform: str
    preference: LibcPreference


BUILD_TEMPLATE = """\"\"\"Python Build Standalone Versions

A mapping of Python version to platform to integrity and URL for Python Build Standalone distributions.
\"\"\"

# AUTO-GENERATED: DO NOT MODIFY
#
# Update using the following command:
#
# ```
# bazel run //python/pex/private:update_python_versions
# ```

PYTHON_BUILD_STANDALONE_VERSIONS = {versions}
"""


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--output",
        type=Path,
        help="The path in which to save results (defaults to scie_python_versions.bzl).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def _workspace_root() -> Path:
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        return Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])

    return Path(__file__).parent.parent.parent.parent


def _rlocation(runfiles: Runfiles, rlocationpath: str) -> Path:
    """Look up a runfile and ensure the file exists

    Args:
        runfiles: The runfiles object
        rlocationpath: The runfile key

    Returns:
        The requested runfile.
    """
    source_repo = None
    if platform.system() == "Windows":
        source_repo = ""
    runfile = runfiles.Rlocation(rlocationpath, source_repo)
    if not runfile:
        raise FileNotFoundError(f"Failed to find runfile: {rlocationpath}")
    path = Path(runfile)
    if not path.exists():
        raise FileNotFoundError(f"Runfile does not exist: ({rlocationpath}) {path}")
    return path


def integrity(hex_str: str) -> str:
    """Convert a sha256 hex value to a Bazel integrity value"""
    # Remove any whitespace and convert from hex to raw bytes
    try:
        raw_bytes = binascii.unhexlify(hex_str.strip())
    except binascii.Error as e:
        raise ValueError(f"Invalid hex input: {e}") from e

    # Convert to base64
    encoded = base64.b64encode(raw_bytes).decode("utf-8")
    return f"sha256-{encoded}"


def _platform_from_asset_name(asset_name: str) -> PlatformInfo | None:
    """Extract platform identifier from Python Build Standalone asset name.

    Examples:
    - cpython-3.11.14+20251028-x86_64-unknown-linux-gnu-install_only.tar.gz -> PlatformInfo("linux-x86_64", LibcPreference.GNU)
    - cpython-3.11.14+20251028-x86_64-unknown-linux-musl-install_only.tar.gz -> PlatformInfo("linux-x86_64", LibcPreference.MUSL)
    - cpython-3.11.14+20251028-armv7-unknown-linux-gnueabihf-install_only.tar.gz -> PlatformInfo("linux-armv7l", LibcPreference.GNUEABIHF)

    Returns:
        PlatformInfo with platform name and libc preference, or None if not recognized.
    """
    # Map of (OS indicators, arch indicators) -> platform name
    platform_mappings = [
        ((("linux-gnu", "linux-musl"), ("x86_64",)), "linux-x86_64"),
        ((("linux-gnu", "linux-musl"), ("aarch64", "arm64")), "linux-aarch64"),
        ((("linux-gnu", "linux-musl"), ("armv7",)), "linux-armv7l"),
        ((("linux-gnu", "linux-musl"), ("ppc64le", "powerpc64")), "linux-powerpc64"),
        ((("linux-gnu", "linux-musl"), ("riscv64",)), "linux-riscv64"),
        ((("linux-gnu", "linux-musl"), ("s390x",)), "linux-s390x"),
        ((("apple-darwin", "macos"), ("x86_64",)), "macos-x86_64"),
        ((("apple-darwin", "macos"), ("aarch64", "arm64")), "macos-aarch64"),
        ((("windows", "pc-windows"), ("x86_64", "x64")), "windows-x86_64"),
    ]

    for (os_indicators, arch_indicators), result in platform_mappings:
        if any(os_ind in asset_name for os_ind in os_indicators) and any(
            arch_ind in asset_name for arch_ind in arch_indicators
        ):
            # Determine preference based on libc/ABI variant
            if "gnueabihf" in asset_name:
                preference = LibcPreference.GNUEABIHF
            elif "linux-gnu" in asset_name:
                preference = LibcPreference.GNU
            elif "gnueabi" in asset_name:
                preference = LibcPreference.GNUEABI
            else:
                preference = LibcPreference.MUSL

            return PlatformInfo(platform=result, preference=preference)

    return None


def _process_version(
    science: Path,
    provider: str,
    python_version: str,
    tmp_path: Path,
) -> dict[str, dict[str, str]] | None:
    """Process a single Python version for a provider.

    Args:
        science: Path to science binary
        provider: Provider name
        python_version: Python version to process
        tmp_path: Temporary directory path

    Returns:
        Version data dict mapping platform -> asset info, or None if failed
    """
    logging.info("Downloading provider info for %s", provider)
    distributions = download_provider_info(science, provider, python_version, tmp_path)

    if not distributions:
        logging.warning(
            "Failed to download distributions for %s %s", provider, python_version
        )
        return None

    version_data = {}

    # Get base_url from distributions
    base_url_obj = distributions.get("base_url", "")
    base_url = base_url_obj if isinstance(base_url_obj, str) else ""

    # Process each distribution asset, preferring gnu builds for Linux
    # Track builds with preference: gnueabihf > gnu > gnueabi > musl
    platform_assets: dict[str, tuple[dict[str, str], LibcPreference]] = {}

    assets = distributions.get("assets", [])
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            result = _process_asset(asset, base_url)
            if result:
                plat, asset_data, preference = result
                # Use this asset if we haven't seen the platform, or if it has higher preference
                if plat not in platform_assets or preference > platform_assets[plat][1]:
                    platform_assets[plat] = (asset_data, preference)
                    logging.debug(
                        "Selected %s (%s) for %s: %s",
                        plat,
                        preference.name.lower(),
                        python_version,
                        asset_data["url"],
                    )

    # Extract just the asset data (without preference value)
    version_data = {
        plat: asset_data for plat, (asset_data, _) in platform_assets.items()
    }

    if version_data:
        logging.info(
            "Found %d platforms for Python %s", len(version_data), python_version
        )
    return version_data if version_data else None


def _process_asset(
    asset: dict[str, object], base_url: str
) -> tuple[str, dict[str, str], LibcPreference] | None:
    """Process a single distribution asset.

    Args:
        asset: Asset dict from distributions JSON
        base_url: Base URL for downloads

    Returns:
        Tuple of (platform, asset_data, preference) or None if asset should be skipped.
        preference indicates build quality: GNUEABIHF > GNU > GNUEABI > MUSL.
    """
    asset_name = asset.get("name", "")
    if (
        not asset_name
        or not isinstance(asset_name, str)
        or not asset_name.endswith(".tar.gz")
    ):
        return None

    platform_info = _platform_from_asset_name(asset_name)
    if not platform_info:
        logging.debug("Could not determine platform for asset: %s", asset_name)
        return None

    # Get SHA256 hash from asset digest
    digest = asset.get("digest", {})
    sha256_hash = digest.get("fingerprint") if isinstance(digest, dict) else None
    if not sha256_hash or not isinstance(sha256_hash, str):
        logging.warning("Asset %s missing fingerprint in digest", asset_name)
        return None

    # Construct URL from base_url and rel_path
    rel_path = asset.get("rel_path", "")
    if not rel_path or not isinstance(rel_path, str):
        logging.warning("Asset %s missing rel_path", asset_name)
        return None

    # URL is {base_url}/{rel_path}
    url = f"{base_url}/{rel_path}"

    return (
        platform_info.platform,
        {
            "url": url,
            "integrity": integrity(sha256_hash),
        },
        platform_info.preference,
    )


def download_provider_info(
    science_binary: Path, provider: str, version: str, tmp_dir: Path
) -> dict[str, Any] | None:
    """Download provider information using science download command.

    Args:
        science_binary: Path to the science binary
        provider: Provider name (e.g., "PythonBuildStandalone")
        version: Python version (e.g., "3.11.14")
        tmp_dir: Temporary directory for downloads

    Returns:
        Parsed distributions JSON data or None if failed
    """
    download_dir = tmp_dir / f"{provider}_{version}"
    download_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(science_binary),
        "download",
        "provider",
        provider,
        str(download_dir),
        "--version",
        version,
    ]

    logging.debug("Running command: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        logging.debug("Science download output: %s", result.stdout)
    except subprocess.CalledProcessError as exc:
        logging.error("Science download failed: %s", exc.stderr)
        return None

    # Look for JSON file in providers/{PROVIDER}/latest/download/distributions-{version}-install_only.json
    json_file = (
        download_dir
        / "providers"
        / provider
        / "latest"
        / "download"
        / f"distributions-{version}-install_only.json"
    )

    if not json_file.exists():
        logging.error("Distributions JSON file does not exist: %s", json_file)
        return None
    logging.debug("Loading distributions from: %s", json_file)
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, dict):
            logging.error("Expected dict, got %s", type(data))
            return None
        return data


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    runfiles = Runfiles.Create()
    if not runfiles:
        raise EnvironmentError("Unable to locate runfiles.")

    science = _rlocation(runfiles, os.environ["SCIE_SCIENCE_BINARY"])

    versions_data = {}

    with tempfile.TemporaryDirectory(prefix="python-versions-") as tmp_dir:
        tmp_path = Path(tmp_dir)

        for python_version in PYTHON_VERSIONS:
            logging.info("Processing Python version: %s", python_version)

            for provider in PROVIDERS:
                version_data = _process_version(
                    science, provider, python_version, tmp_path
                )
                if version_data:
                    versions_data[python_version] = version_data

    # Determine output file
    if args.output:
        output_file = args.output
    else:
        output_file = _workspace_root() / "python/pex/private/scie_python_versions.bzl"

    # Format the output
    versions_json = json.dumps(versions_data, indent=4)

    # Write to file
    logging.debug("Writing to %s", output_file)
    output_file.write_text(
        BUILD_TEMPLATE.format(versions=versions_json), encoding="utf-8"
    )
    logging.info(
        "Done. Generated %s with %d Python versions", output_file, len(versions_data)
    )


if __name__ == "__main__":
    main()
