#!/usr/bin/env python3
"""Fetch the exact public Marketplace rules into a local reference cache.

The manifest contains URLs and hashes, never third-party source. Downloads use
unauthenticated HTTPS, reject redirects, and are only written after every missing
file passes its pinned hash. No downloaded source is executed or altered.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import ssl
import tempfile
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/upstream/security-rules-manifest.json"
DEFAULT_DIRECTORY = ROOT / ".reference-source/marketplace/validation/semgrep-rules"
MANIFEST_SHA256 = "893d414e028333ad356c165fd6317efa383ff2896f159068608a63e04fd2c0eb"
REPOSITORY = "https://github.com/frappe/marketplace"
COMMIT = "cb1a58adfacbe9d8e0e4a4d5c7d1ef7786a05e6a"
SOURCE_PREFIX = "validation/semgrep-rules/"
RAW_PREFIX = "https://raw.githubusercontent.com/frappe/marketplace/" + COMMIT + "/" + SOURCE_PREFIX
MAX_RULE_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
NETWORK_TIMEOUT = 15
RULE_PATHS = frozenset({
    "frappe-extra/code_quality.yml", "frappe-extra/report.yml",
    "frappe-extra/security/whitelisted.yml", "frappe-extra/translate.yml",
    "frappe-extra/ux.yml", "marketplace-security/correctness.yml",
    "marketplace-security/security/authorization.yml",
    "marketplace-security/security/command_execution.yml",
    "marketplace-security/security/filesystem.yml",
    "marketplace-security/security/format_string_injection.yml",
    "marketplace-security/security/rce.yml", "marketplace-security/security/sql.yml",
})


class RuleFetchError(ValueError):
    """A manifest, network response or local cache failed verification."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_manifest(manifest):
    if (not isinstance(manifest, dict)
            or set(manifest) != {"schema_version", "repository", "commit", "source_prefix", "files"}
            or manifest.get("schema_version") != 1
            or manifest.get("repository") != REPOSITORY
            or manifest.get("commit") != COMMIT
            or manifest.get("source_prefix") != SOURCE_PREFIX):
        raise RuleFetchError("Manifest does not describe the pinned official rule set.")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != len(RULE_PATHS):
        raise RuleFetchError("Manifest must contain every pinned rule exactly once.")
    found = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "url", "sha256"}:
            raise RuleFetchError("Invalid manifest rule entry.")
        path = entry["path"]
        if (not isinstance(path, str) or path not in RULE_PATHS or path in found
                or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):
            raise RuleFetchError("Manifest contains a duplicate or unapproved rule path.")
        if entry["url"] != RAW_PREFIX + path:
            raise RuleFetchError("Rule URL must use the exact official HTTPS host and commit.")
        if not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise RuleFetchError("Rule hash is not a SHA-256 digest.")
        found.add(path)
    return manifest


def load_manifest(path=MANIFEST):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuleFetchError("Manifest must be a regular local file.")
    with path.open("rb") as stream:
        body = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(body) > MAX_MANIFEST_BYTES or sha256(body) != MANIFEST_SHA256:
        raise RuleFetchError("Manifest differs from its pinned SHA-256 digest.")
    try:
        manifest = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise RuleFetchError("Manifest is not valid JSON.") from error
    return validate_manifest(manifest)


def _reject_symlink_path(path):
    for component in (path, *path.parents):
        if component.is_symlink():
            raise RuleFetchError("Reference cache paths must not contain symlinks.")


def _cache_hashes(manifest, directory, require_complete):
    directory = Path(directory).absolute()
    _reject_symlink_path(directory)
    expected = {entry["path"]: entry["sha256"] for entry in validate_manifest(manifest)["files"]}
    if directory.exists() and not directory.is_dir():
        raise RuleFetchError("Reference cache must be a directory.")
    actual = {}
    if directory.exists():
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise RuleFetchError("Reference cache paths must not contain symlinks.")
            if path.is_dir():
                continue
            relative = path.relative_to(directory).as_posix()
            if relative not in expected or not path.is_file():
                raise RuleFetchError("Reference cache contains an unexpected file.")
            with path.open("rb") as stream:
                body = stream.read(MAX_RULE_BYTES + 1)
            if len(body) > MAX_RULE_BYTES or sha256(body) != expected[relative]:
                raise RuleFetchError("Existing reference rule differs from its pinned hash: " + relative)
            actual[relative] = expected[relative]
    if require_complete and set(actual) != set(expected):
        raise RuleFetchError("Reference cache is incomplete; fetch the pinned rules first.")
    return actual


def verify_rules_directory(manifest, directory=DEFAULT_DIRECTORY):
    """Return relative-path hashes only after the complete cache verifies."""
    return _cache_hashes(manifest, directory, require_complete=True)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, target):
        raise RuleFetchError("Rule download redirects are forbidden.")


def _download(entry):
    # Explicit handlers avoid proxy credentials, cookies and authentication state.
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(),
                                        urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(entry["url"], headers={"Accept": "text/plain"}, method="GET")
    try:
        with opener.open(request, timeout=NETWORK_TIMEOUT) as response:
            if response.status != 200 or response.geturl() != entry["url"]:
                raise RuleFetchError("Rule response must come directly from the pinned URL.")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdecimal() or int(length) > MAX_RULE_BYTES):
                raise RuleFetchError("Rule response exceeds the download limit.")
            body = response.read(MAX_RULE_BYTES + 1)
    except (OSError, urllib.error.URLError) as error:
        raise RuleFetchError("Unable to fetch the pinned rule: " + entry["path"]) from error
    if len(body) > MAX_RULE_BYTES:
        raise RuleFetchError("Rule response exceeds the download limit.")
    if sha256(body) != entry["sha256"]:
        raise RuleFetchError("Downloaded rule differs from its pinned hash: " + entry["path"])
    return body


def _atomic_write(path, body):
    _reject_symlink_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".rule-", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic creation never replaces a concurrent conflicting cache entry.
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != body:
                raise RuleFetchError("Reference cache changed while writing a rule.")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fetch_rules(manifest, directory=DEFAULT_DIRECTORY):
    """Verify any existing cache, then fetch and atomically add missing files."""
    manifest = validate_manifest(manifest)
    directory = Path(directory).absolute()
    existing = _cache_hashes(manifest, directory, require_complete=False)
    # Validate all downloads before adding any file to the reference cache.
    pending = [(entry["path"], _download(entry)) for entry in manifest["files"]
               if entry["path"] not in existing]
    _cache_hashes(manifest, directory, require_complete=False)
    for relative, body in pending:
        _atomic_write(directory / relative, body)
    hashes = verify_rules_directory(manifest, directory)
    return {"verified_rule_count": len(hashes), "downloaded_rule_count": len(pending),
            "validator_commit": COMMIT}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--rules-directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    try:
        result = fetch_rules(load_manifest(args.manifest), args.rules_directory)
    except RuleFetchError as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
