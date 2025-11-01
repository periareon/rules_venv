"""A script for fetching all available versions of scie tools (science, jump, ptex) and pex."""

import argparse
import base64
import binascii
import json
import logging
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import urlopen

SCIE_RELEASE_NAME_REGEX = r"^v(\d+\.\d+\.\d+.*)$"

SCIE_PLATFORMS = [
    "linux-aarch64",
    "linux-armv7l",
    "linux-powerpc64",
    "linux-riscv64",
    "linux-s390x",
    "linux-x86_64",
    "macos-aarch64",
    "macos-x86_64",
    "windows-x86_64",
]

REQUEST_HEADERS = {"User-Agent": "curl/8.7.1"}  # Set the User-Agent header

# Mapping of tool type to configuration
TOOL_CONFIG = {
    "science": {
        "repo": "a-scie/lift",
        "artifact_prefix": "science-fat",
        "variable_name": "SCIE_SCIENCE_VERSIONS",
        "display_name": "scie science",
        "output_file": "scie_science_versions.bzl",
        "bazel_target": "update_scie_science_versions",
    },
    "jump": {
        "repo": "a-scie/jump",
        "artifact_prefix": "scie-jump",
        "variable_name": "SCIE_JUMP_VERSIONS",
        "display_name": "scie jump",
        "output_file": "scie_jump_versions.bzl",
        "bazel_target": "update_scie_jump_versions",
    },
    "ptex": {
        "repo": "a-scie/ptex",
        "artifact_prefix": "ptex",
        "variable_name": "SCIE_PTEX_VERSIONS",
        "display_name": "scie ptex",
        "output_file": "scie_ptex_versions.bzl",
        "bazel_target": "update_scie_ptex_versions",
    },
    "pex": {
        "repo": "pex-tool/pex",
        "variable_name": "PEX_VERSIONS",
        "display_name": "pex",
        "output_file": "pex_versions.bzl",
        "bazel_target": "update_pex_versions",
    },
}

GITHUB_API_TEMPLATE = "https://api.github.com/repos/{repo}/releases?page={page}"


def _workspace_root() -> Path:
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        return Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])

    return Path(__file__).parent.parent.parent.parent


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "tool",
        choices=["science", "jump", "ptex", "pex"],
        help="The tool to fetch versions for (science, jump, ptex, or pex).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="The path in which to save results (defaults to tool-specific output file).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def fetch_sha256(sha256_url: str, artifact_name: str) -> str | None:
    """Parse sha256 hash from a .sha256 file for a specific artifact."""
    req = urllib.request.Request(sha256_url, headers=REQUEST_HEADERS)
    logging.debug("Fetching sha256 file: %s", sha256_url)
    try:
        with urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Format: {hash} *{file}
                parts = line.split()
                if len(parts) >= 2 and parts[1] == f"*{artifact_name}":
                    return str(parts[0])
                # Also handle format without asterisk: {hash} {file}
                if len(parts) >= 2 and parts[1] == artifact_name:
                    return str(parts[0])
    except HTTPError as exc:
        logging.debug("Failed to fetch sha256 file %s: %s", sha256_url, exc)
        return None
    return None


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


def _process_release_artifacts(
    release: dict[str, Any],
    version: str,
    platforms: list[str],
    artifact_prefix: str,
) -> dict[str, dict[str, str]]:
    """Process artifacts for a single release."""
    assets_map = {asset["name"]: asset for asset in release["assets"]}
    artifacts = {}

    for platform in platforms:
        artifact_name = f"{artifact_prefix}-{platform}"
        if platform.startswith("windows"):
            artifact_name += ".exe"
        sha256_name = f"{artifact_name}.sha256"

        if artifact_name not in assets_map or sha256_name not in assets_map:
            logging.debug(
                "Artifact %s or %s not found for version %s",
                artifact_name,
                sha256_name,
                version,
            )
            continue

        sha256_url = assets_map[sha256_name]["browser_download_url"]
        sha256_hash = fetch_sha256(sha256_url, artifact_name)

        if not sha256_hash:
            logging.debug("Failed to parse sha256 for %s", artifact_name)
            continue

        artifacts[platform] = {
            "url": assets_map[artifact_name]["browser_download_url"],
            "integrity": integrity(sha256_hash),
        }
        logging.debug(
            "Matched artifact for %s: %s (integrity: %s)",
            platform,
            artifact_name,
            artifacts[platform]["integrity"],
        )

    return artifacts


def _process_pex_release_artifacts(
    release: dict[str, Any],
    version: str,
    platforms: list[str],
) -> dict[str, dict[str, str]]:
    """Process artifacts for a single pex release (platform-specific .pex files)."""
    assets_map = {asset["name"]: asset for asset in release["assets"]}
    artifacts = {}

    for platform in platforms:
        # pex files are named pex-{platform} (e.g., pex-linux-x86_64, pex-macos-aarch64)
        artifact_name = f"pex-{platform}"
        sha256_name = f"{artifact_name}.sha256"

        if artifact_name not in assets_map or sha256_name not in assets_map:
            logging.debug(
                "Artifact %s or %s not found for version %s",
                artifact_name,
                sha256_name,
                version,
            )
            continue

        sha256_url = assets_map[sha256_name]["browser_download_url"]
        sha256_hash = fetch_sha256(sha256_url, artifact_name)

        if not sha256_hash:
            logging.debug("Failed to parse sha256 for %s", artifact_name)
            continue

        artifacts[platform] = {
            "url": assets_map[artifact_name]["browser_download_url"],
            "integrity": integrity(sha256_hash),
        }
        logging.debug(
            "Matched artifact for %s: %s (integrity: %s)",
            platform,
            artifact_name,
            artifacts[platform]["integrity"],
        )

    return artifacts


def _handle_rate_limit(exc: HTTPError) -> None:
    """Handle GitHub API rate limiting."""
    if exc.code != 403:
        raise exc

    reset_time = exc.headers.get("x-ratelimit-reset")
    if not reset_time:
        raise exc

    sleep_duration = float(reset_time) - time.time()
    if sleep_duration < 0.0:
        return

    logging.warning("%s", exc.msg)
    logging.debug("Waiting %ss for reset", sleep_duration)
    time.sleep(sleep_duration)


def query_releases(
    platforms: list[str],
    repo: str,
    artifact_prefix: str,
) -> dict[str, dict[str, dict[str, str]]]:
    """Query GitHub releases and extract scie binaries for each platform."""
    page = 1
    releases_data = {}
    version_regex = re.compile(SCIE_RELEASE_NAME_REGEX)

    while True:
        url = urlparse(GITHUB_API_TEMPLATE.format(repo=repo, page=page))
        req = urllib.request.Request(url.geturl(), headers=REQUEST_HEADERS)
        logging.debug("Releases url: %s", url.geturl())

        try:
            with urlopen(req) as data:
                json_data = json.loads(data.read())
                if not json_data:
                    break

                for release in json_data:
                    regex = version_regex.match(release["tag_name"])
                    if not regex:
                        continue

                    version = regex.group(1)
                    logging.debug(
                        "Processing %s (tag: %s)", version, release["tag_name"]
                    )

                    artifacts = _process_release_artifacts(
                        release, version, platforms, artifact_prefix
                    )

                    if artifacts:
                        logging.debug(
                            "Matched %s artifacts for version %s",
                            len(artifacts),
                            version,
                        )
                        releases_data[version] = artifacts
                    else:
                        logging.debug("No artifacts matched for version %s", version)

            page += 1
            time.sleep(0.5)
        except HTTPError as exc:
            _handle_rate_limit(exc)

    return releases_data


def query_pex_releases(
    repo: str, platforms: list[str]
) -> dict[str, dict[str, dict[str, str]]]:
    """Query GitHub releases and extract pex platform-specific binaries."""
    page = 1
    releases_data = {}
    version_regex = re.compile(SCIE_RELEASE_NAME_REGEX)

    while True:
        url = urlparse(GITHUB_API_TEMPLATE.format(repo=repo, page=page))
        req = urllib.request.Request(url.geturl(), headers=REQUEST_HEADERS)
        logging.debug("Releases url: %s", url.geturl())

        try:
            with urlopen(req) as data:
                json_data = json.loads(data.read())
                if not json_data:
                    break

                for release in json_data:
                    regex = version_regex.match(release["tag_name"])
                    if not regex:
                        continue

                    version = regex.group(1)
                    logging.debug(
                        "Processing %s (tag: %s)", version, release["tag_name"]
                    )

                    artifacts = _process_pex_release_artifacts(
                        release, version, platforms
                    )

                    if artifacts:
                        logging.debug(
                            "Matched %s pex artifacts for version %s",
                            len(artifacts),
                            version,
                        )
                        releases_data[version] = artifacts
                    else:
                        logging.debug(
                            "No pex artifacts matched for version %s", version
                        )

            page += 1
            time.sleep(0.5)
        except HTTPError as exc:
            _handle_rate_limit(exc)

    return releases_data


_BUILD_TEMPLATE = """\
\"\"\"{title} Versions

{content_description}
\"\"\"

# AUTO-GENERATED: DO NOT MODIFY
#
# Update using the following command:
#
# ```
# bazel run //python/pex/private:update_pex_versions -- {tool_arg}
# ```

{variable_name} = {versions}
"""


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    config = TOOL_CONFIG[args.tool]

    # Determine output file
    output_file = args.output
    if not output_file:
        output_file = _workspace_root() / "python/pex/private" / config["output_file"]

    logging.info("Fetching %s versions", args.tool)

    # Query releases from GitHub
    if args.tool == "pex":
        # pex uses pex-{platform} naming convention
        releases = query_pex_releases(
            repo=config["repo"],
            platforms=SCIE_PLATFORMS,
        )
    else:
        # scie tools use {artifact_prefix}-{platform} naming convention
        releases = query_releases(
            platforms=SCIE_PLATFORMS,
            repo=config["repo"],
            artifact_prefix=config["artifact_prefix"],
        )

    content_description = (
        "A mapping of platform to integrity of the binary for said platform "
        f"for each version of {config['display_name']} available."
    )

    logging.info("Found %d releases", len(releases))

    # Write to file
    logging.debug("Writing to %s", output_file)
    output_file.write_text(
        _BUILD_TEMPLATE.format(
            title=config["display_name"].title(),
            content_description=content_description,
            tool_arg=args.tool,
            variable_name=config["variable_name"],
            versions=json.dumps(releases, indent=4, sort_keys=True),
        ),
        encoding="utf-8",
    )
    logging.info("Done")


if __name__ == "__main__":
    main()
