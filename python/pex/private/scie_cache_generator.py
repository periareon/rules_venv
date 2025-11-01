"""Generate a scie science cache directory structure."""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

# TODO: These values are hard-coded in pex and need to match the current version
# being used. For now we these versions are always hard-coded regardless of the
# versions passed in from the toolchain.
PTEX_VERSION = "1.7.0"
SCIE_JUMP_VERSION = "1.8.0"


class InterpreterInfo(NamedTuple):
    """Information about a Python interpreter archive."""

    name: str
    version_part: str
    version_date: str
    target_triple: str
    major_minor_version: str
    size: int
    sha256_hex: str


class ScieBinaries(NamedTuple):
    """Collection of scie tool binaries."""

    science: Path
    jump: Path
    ptex: Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--output_dir",
        type=Path,
        required=True,
        help="The output directory for the scies cache structure.",
    )
    parser.add_argument(
        "--science",
        type=Path,
        required=True,
        help="Path to the scie science binary.",
    )
    parser.add_argument(
        "--jump",
        type=Path,
        required=True,
        help="Path to the scie jump binary.",
    )
    parser.add_argument(
        "--ptex",
        type=Path,
        required=True,
        help="Path to the scie ptex binary.",
    )
    parser.add_argument(
        "--interpreter",
        type=Path,
        required=True,
        help="Path to the Python interpreter archive.",
    )
    parser.add_argument(
        "--interpreter_version",
        type=str,
        required=True,
        help="The expected Python interpreter version (e.g., '3.11').",
    )

    return parser.parse_args()


def verify_download(
    science: Path,
    target: str,
    output_dir: Path,
    extra_args: list[str] | None = None,
) -> None:
    """Run science download and verify it succeeds."""
    cmd = [str(science), "download"]
    if target in ["PythonBuildStandalone", "Pypy"]:
        cmd.extend(["provider", target])
    else:
        cmd.append(target)

    if extra_args:
        cmd.extend(extra_args)

    cmd.append(str(output_dir))

    logging.debug("Verifying download with command: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode:
        logging.error("Failed to download: %s", target)
        raise RuntimeError(result.stdout)


def compute_url_hash(url: str) -> str:
    """Compute the URL hash used by science's cache."""
    return hashlib.sha256(url.encode()).hexdigest()


def get_filename_from_url(url: str, fallback_name: str) -> str:
    """Extract filename from URL path, matching science's behavior.

    Args:
        url: The URL to extract filename from
        fallback_name: Fallback filename if URL doesn't contain one

    Returns:
        The extracted filename
    """
    # Science uses os.path.basename(url.info.path) to get the filename from cache
    # The url.info.path is from urllib.parse.urlparse(), which returns the path as-is (without decoding)
    # So we need to store the filename exactly as it appears in the URL path (not URL-encoded)
    url_path = urlparse(url).path
    # Extract the filename from the URL path (this matches what science does)
    filename = os.path.basename(url_path)
    # For paths that end with "/", use the last non-empty segment
    if not filename and url_path:
        parts = [p for p in url_path.split("/") if p]
        if parts:
            filename = parts[-1]
    # Only use fallback_name if we truly have no filename
    if not filename:
        filename = fallback_name
    # Note: We do NOT URL-encode the filename because science expects the raw basename
    # from the URL path (e.g., "cpython-3.11.14+20251028-..." not "cpython-3.11.14%2B20251028-...")
    return filename


def populate_hash_cache(
    cache_base_dir: Path,
    url: str,
    source_file: Path,
    digest_json: dict[str, str | int] | None = None,
    ttl: bool | None = None,
) -> None:
    """Populate science's hash-based cache directory with a file.

    Creates the structure: {cache_base_dir}/downloads/1/{url_hash}/_/{filename}
    Optionally creates digest.json in: {cache_base_dir}/downloads/1/{url_hash}/+/digest.json
    Optionally creates a .ttl file to prevent science from clearing the cache entry

    Args:
        cache_base_dir: Base cache directory (e.g., {pex_root}/scies/0/science/{version}/cache)
        url: The URL that science will request
        source_file: The file to cache
        digest_json: Optional digest JSON to store in the +/ directory
        ttl: If provided, creates a .ttl file with far-future expiry
    """
    url_hash = compute_url_hash(url)
    cache_dir = cache_base_dir / "downloads" / "1" / url_hash
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Get filename from URL path
    filename = get_filename_from_url(url, source_file.name)

    # Copy file to cache
    cache_file = cache_dir / "_" / filename
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, cache_file)

    # Store digest.json if provided
    if digest_json:
        aux_dir = cache_dir / "+"
        aux_dir.mkdir(parents=True, exist_ok=True)
        (aux_dir / "digest.json").write_text(
            json.dumps(digest_json, indent=2),
            encoding="utf-8",
        )

    # Create .ttl file if TTL is expected (prevents science from clearing the cache)
    # Science checks for .ttl files and clears cache entries if they're missing or expired
    # Note: TTL format uses 2-digit year (%y), where 00-68 maps to 2000-2068
    # We use 68 (2068) as a far-future date to prevent science from clearing the cache
    if ttl is not None:
        ttl_file = cache_dir.with_suffix(".ttl")
        # Set expiry to far future (year 2068) to prevent science from clearing the cache
        # Using 2-digit year format: 12/31/68 means Dec 31, 2068
        far_future = datetime(2068, 12, 31, 23, 59, 59)
        ttl_file.write_text(far_future.strftime("%m/%d/%y %H:%M:%S"))

    logging.debug("Cached %s -> %s (hash: %s)", url, cache_file, url_hash)


def get_binary_version(binary_path: Path) -> str:
    """Run `--version` on the given binary and return the version string."""
    result = subprocess.run(
        [str(binary_path), "--version"],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode:
        logging.error("%s", result.stdout)
        raise RuntimeError(f"Failed to query {binary_path.name} version.")

    return result.stdout.strip()


def parse_interpreter_filename(interpreter_name: str) -> tuple[str, str, str, str]:
    """Parse Python interpreter archive filename.

    Args:
        interpreter_name: Filename like cpython-3.11.14+20251028-aarch64-apple-darwin-install_only.tar.gz

    Returns:
        Tuple of (version_part, version_date, target_triple, major_minor_version)
        E.g., ("3.11.14", "20251028", "aarch64-apple-darwin", "3.11")
    """
    if not interpreter_name.startswith("cpython-") or not interpreter_name.endswith(
        "-install_only.tar.gz"
    ):
        raise ValueError(
            f"Unexpected Python interpreter archive name: {interpreter_name}"
        )

    # Extract version, date, and target_triple from filename
    # Format: cpython-X.Y.Z+{DATE}-{TARGET_TRIPLE}-install_only.tar.gz
    name_without_ext = interpreter_name.replace("-install_only.tar.gz", "")
    parts = name_without_ext.split("+")
    if len(parts) != 2:
        raise ValueError(f"Could not parse version date from: {interpreter_name}")

    version_part = parts[0].replace("cpython-", "")  # e.g., "3.11.14"
    date_and_triple = parts[1]  # e.g., "20251028-aarch64-apple-darwin"
    version_date = date_and_triple.split("-")[0]  # e.g., "20251028"
    target_triple = "-".join(
        date_and_triple.split("-")[1:]
    )  # e.g., "aarch64-apple-darwin"

    # Extract major.minor version (e.g., "3.11" from "3.11.14")
    version_parts = version_part.split(".")
    if len(version_parts) < 2:
        raise ValueError(f"Could not parse Python version from: {version_part}")
    major_minor_version = f"{version_parts[0]}.{version_parts[1]}"  # e.g., "3.11"

    return version_part, version_date, target_triple, major_minor_version


def cache_scie_binary(
    cache_base_dir: Path,
    binary_path: Path,
    binary_name: str,
    version: str,
    repo_name: str,
) -> None:
    """Cache a scie binary (jump or ptex) with both versioned and latest URLs.

    Args:
        cache_base_dir: Base cache directory
        binary_path: Path to the binary file
        binary_name: Name of the binary file
        version: Version string (e.g., "1.8.0")
        repo_name: GitHub repo name (e.g., "jump" or "ptex")
    """
    binary_sha256 = hashlib.sha256(binary_path.read_bytes()).hexdigest()
    binary_size = binary_path.stat().st_size

    # Cache version-specific URL (what pex requests when version is provided)
    url_versioned = f"https://github.com/a-scie/{repo_name}/releases/download/v{version}/{binary_name}"
    populate_hash_cache(
        cache_base_dir,
        url_versioned,
        binary_path,
        digest_json={
            "hash": binary_sha256,
            "size": binary_size,
        },
    )

    # Also cache latest/download URL in case GitHub redirects or pex uses it
    url_latest = (
        f"https://github.com/a-scie/{repo_name}/releases/latest/download/{binary_name}"
    )
    populate_hash_cache(
        cache_base_dir,
        url_latest,
        binary_path,
        digest_json={
            "hash": binary_sha256,
            "size": binary_size,
        },
        ttl=True,
    )


def cache_github_api_response(
    cache_base_dir: Path,
    interpreter_name: str,
    version_date: str,
    interpreter_size: int,
) -> None:
    """Cache the GitHub API response for python-build-standalone.

    Args:
        cache_base_dir: Base cache directory
        interpreter_name: Name of the interpreter archive
        version_date: Release date tag
        interpreter_size: Size of the interpreter archive
    """
    api_url = (
        "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
    )
    logging.debug("Generating GitHub API response for: %s", api_url)

    # Create a mock GitHub API response JSON that satisfies science's expectations
    interpreter_download_url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{version_date}/{interpreter_name}"
    sha256sums_url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{version_date}/SHA256SUMS"

    api_response_json = {
        "tag_name": version_date,
        "name": f"Python Build Standalone {version_date}",
        "published_at": f"{version_date[:4]}-{version_date[4:6]}-{version_date[6:8]}T00:00:00Z",
        "html_url": f"https://github.com/astral-sh/python-build-standalone/releases/tag/{version_date}",
        "assets_url": f"https://api.github.com/repos/astral-sh/python-build-standalone/releases/{version_date}/assets",
        "assets": [
            {
                "name": interpreter_name,
                "browser_download_url": interpreter_download_url,
                "size": interpreter_size,
            },
            {
                "name": "SHA256SUMS",
                "browser_download_url": sha256sums_url,
                "size": 0,  # Size doesn't matter for SHA256SUMS lookup
            },
        ],
    }

    api_response_data = json.dumps(api_response_json, indent=2).encode("utf-8")

    # Cache the GitHub API response
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_api_latest = tmp_dir / "latest"
    tmp_api_latest.write_bytes(api_response_data)

    try:
        api_url_hash = compute_url_hash(api_url)
        # API endpoint has TTL of 5 days
        populate_hash_cache(cache_base_dir, api_url, tmp_api_latest, ttl=True)
        expected_cache_path = (
            cache_base_dir / "downloads" / "1" / api_url_hash / "_" / "latest"
        )

        logging.debug(
            "Cached GitHub API response at hash: %s -> %s",
            api_url_hash,
            expected_cache_path,
        )
        # Verify the file was created
        if not expected_cache_path.exists():
            raise RuntimeError(
                f"Failed to create cache file at expected path: {expected_cache_path}."
            )
        # Verify it's a JSON file
        try:
            json.loads(expected_cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Cached API response is not valid JSON: {e}") from e
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def cache_sha256sums(
    cache_base_dir: Path,
    version_date: str,
    interpreter_name: str,
    interpreter_sha256_hex: str,
) -> None:
    """Cache the SHA256SUMS file.

    Args:
        cache_base_dir: Base cache directory
        version_date: Release date tag
        interpreter_name: Name of the interpreter archive
        interpreter_sha256_hex: SHA256 hash of the interpreter
    """
    sha256sums_url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{version_date}/SHA256SUMS"
    sha256sums_content = f"{interpreter_sha256_hex}  {interpreter_name}\n".encode(
        "utf-8"
    )
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp_sha256sums:
        tmp_sha256sums.write(sha256sums_content)
        tmp_sha256sums_path = Path(tmp_sha256sums.name)

    try:
        # SHA256SUMS has no TTL
        populate_hash_cache(cache_base_dir, sha256sums_url, tmp_sha256sums_path)
        logging.debug("Cached SHA256SUMS file")
    finally:
        tmp_sha256sums_path.unlink()


def get_interpreter_info(
    interpreter: Path,
    expected_version: str | None = None,
) -> InterpreterInfo:
    """Extract interpreter information and compute hash.

    Args:
        interpreter: Path to the Python interpreter archive
        expected_version: Optional expected major.minor version (e.g., '3.11')

    Returns:
        InterpreterInfo with parsed details from the archive
    """
    interpreter_name = interpreter.name
    version_part, version_date, target_triple, major_minor_version = (
        parse_interpreter_filename(interpreter_name)
    )

    # Validate version if expected_version is provided
    if expected_version and major_minor_version != expected_version:
        raise ValueError(
            f"Python interpreter version '{major_minor_version}' != expected '{expected_version}' (archive: {interpreter_name})"
        )

    interpreter_size = interpreter.stat().st_size
    interpreter_sha256_hex = hashlib.sha256(interpreter.read_bytes()).hexdigest()

    return InterpreterInfo(
        name=interpreter_name,
        version_part=version_part,
        version_date=version_date,
        target_triple=target_triple,
        major_minor_version=major_minor_version,
        size=interpreter_size,
        sha256_hex=interpreter_sha256_hex,
    )


def _build_distributions_json(interpreter_info: InterpreterInfo) -> dict[str, object]:
    """Build the distributions JSON structure.

    Args:
        interpreter_info: Information about the current interpreter.

    Returns:
        The distributions JSON dict
    """
    return {
        "assets": [
            {
                "digest": {
                    "fingerprint": interpreter_info.sha256_hex,
                    "size": interpreter_info.size,
                },
                "file_type": "tar.gz",
                "name": interpreter_info.name,
                "rel_path": f"download/{interpreter_info.version_date}/{interpreter_info.name}",
                "target_triple": interpreter_info.target_triple,
                "version": interpreter_info.version_part,
            }
        ],
        "base_url": "https://github.com/astral-sh/python-build-standalone/releases",
        "release": interpreter_info.version_date,
    }


def cache_distributions_json(
    cache_base_dir: Path,
    major_minor_version: str,
    dist_json: dict[str, object],
) -> None:
    """Cache the distributions JSON file.

    Args:
        cache_base_dir: Base cache directory
        major_minor_version: Major.minor version (e.g., "3.11")
        dist_json: The distributions JSON dict to cache
    """
    # Create JSON file in temp location for caching
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp_json:
        json.dump(dist_json, tmp_json, indent=2)
        tmp_json_path = Path(tmp_json.name)

    try:
        # Populate hash cache for distributions JSON file
        json_url = f"https://github.com/astral-sh/python-build-standalone/releases/latest/download/distributions-{major_minor_version}-install_only.json"
        populate_hash_cache(cache_base_dir, json_url, tmp_json_path)
    finally:
        tmp_json_path.unlink()


def generate_scie_cache(
    *,
    scie_download_dir: Path,
    scie_binaries: ScieBinaries,
    interpreter: Path,
    expected_interpreter_version: str,
) -> None:
    """Generate a scie science cache directory structure.

    Populates science's hash-based cache directory ({cache_dir}/downloads/1/{url_hash}/_/{filename})
    with all required files using the default GitHub URLs that science requests. This allows science
    to find files automatically in its cache without needing --scie-assets-base-url.

    Args:
        scie_download_dir: The output directory (will contain scies cache structure).
        scie_binaries: Collection of scie tool binaries (science, jump, ptex).
        interpreter: Path to the Python interpreter archive.
        expected_interpreter_version: Expected Python interpreter version string (e.g., '3.11').
    """
    # Get science version and construct cache directory
    science_ver = get_binary_version(scie_binaries.science)
    cache_base_dir = (
        scie_download_dir
        / science_ver.partition(".")[0]
        / "science"
        / science_ver
        / "cache"
    )

    # Cache jump binary (both versioned and latest URLs)
    cache_scie_binary(
        cache_base_dir,
        scie_binaries.jump,
        scie_binaries.jump.name,
        SCIE_JUMP_VERSION,
        "jump",
    )

    # Cache ptex binary (both versioned and latest URLs)
    cache_scie_binary(
        cache_base_dir,
        scie_binaries.ptex,
        scie_binaries.ptex.name,
        PTEX_VERSION,
        "ptex",
    )

    # Extract and validate interpreter information
    interp = get_interpreter_info(interpreter, expected_interpreter_version)

    # Cache GitHub API response
    cache_github_api_response(
        cache_base_dir, interp.name, interp.version_date, interp.size
    )

    # Cache SHA256SUMS file
    cache_sha256sums(
        cache_base_dir, interp.version_date, interp.name, interp.sha256_hex
    )

    # Cache interpreter archive
    populate_hash_cache(
        cache_base_dir,
        f"https://github.com/astral-sh/python-build-standalone/releases/download/{interp.version_date}/{interp.name}",
        interpreter,
        digest_json={
            "hash": interp.sha256_hex,
            "size": interp.size,
        },
    )

    # Cache distributions JSON
    cache_distributions_json(
        cache_base_dir,
        interp.major_minor_version,
        _build_distributions_json(
            interpreter_info=interp,
        ),
    )

    logging.debug("Generated hash-based cache at: %s", cache_base_dir)

    # Verify the cache directory by running science download for all components
    # This ensures the cache structure is correct and science can use it
    # We download to a temporary directory and then discard it - this validates the cache structure
    with tempfile.TemporaryDirectory() as temp_dir:
        # Verify PythonBuildStandalone provider (uses default GitHub URL)
        verify_download(
            science=scie_binaries.science,
            target="PythonBuildStandalone",
            output_dir=Path(temp_dir),
            extra_args=[
                "--version",
                interp.major_minor_version,
            ],
        )

        logging.debug("All cache verifications succeeded")


def main() -> None:
    """The main entrypoint."""
    args = parse_args()

    is_debug = (
        "RULES_VENV_PEX_PROCESS_WRAPPER_DEBUG" in os.environ
        or "RULES_VENV_DEBUG" in os.environ
    )

    if is_debug:
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            level=logging.DEBUG,
        )

    scie_binaries = ScieBinaries(
        science=args.science,
        jump=args.jump,
        ptex=args.ptex,
    )

    generate_scie_cache(
        scie_download_dir=args.output_dir,
        scie_binaries=scie_binaries,
        interpreter=args.interpreter,
        expected_interpreter_version=args.interpreter_version,
    )


if __name__ == "__main__":
    main()
