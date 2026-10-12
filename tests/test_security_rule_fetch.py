"""Offline security checks; responses contain our synthetic text, never vendor rules."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import ssl

import pytest


@pytest.fixture
def fetcher():
    path = Path(__file__).parents[1] / "tools/fetch_security_rules.py"
    spec = importlib.util.spec_from_file_location("security_rule_fetcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synthetic(fetcher):
    bodies = {path: ("synthetic offline response: " + path + "\n").encode()
              for path in fetcher.RULE_PATHS}
    manifest = {"schema_version": 1, "repository": fetcher.REPOSITORY,
                "commit": fetcher.COMMIT, "source_prefix": fetcher.SOURCE_PREFIX,
                "files": [{"path": path, "url": fetcher.RAW_PREFIX + path,
                           "sha256": fetcher.sha256(bodies[path])} for path in sorted(bodies)]}
    return manifest, bodies


class Response(io.BytesIO):
    def __init__(self, body, url, status=200, headers=None):
        super().__init__(body)
        self.url, self.status, self.headers = url, status, headers or {}
        self.read_limits = []

    def geturl(self):
        return self.url

    def read(self, limit=-1):
        self.read_limits.append(limit)
        return super().read(limit)


def mock_network(fetcher, monkeypatch, bodies, response_change=None):
    calls, handlers, responses = [], [], []

    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            path = request.full_url[len(fetcher.RAW_PREFIX):]
            response = Response(bodies[path], request.full_url)
            if response_change:
                response_change(path, response)
            responses.append(response)
            return response

    def build(*values):
        handlers.extend(values)
        return Opener()

    monkeypatch.setattr(fetcher.urllib.request, "build_opener", build)
    return calls, handlers, responses


def test_committed_manifest_matches_the_recorded_official_rule_hashes(fetcher):
    manifest = fetcher.load_manifest()
    source = json.loads((fetcher.ROOT / "docs/upstream/source-verification.json").read_text())
    recorded = {item["url"]: item["sha256"] for item in source["downloads"]}
    assert {entry["path"] for entry in manifest["files"]} == fetcher.RULE_PATHS
    assert all(recorded[entry["url"]] == entry["sha256"] for entry in manifest["files"])


def test_manifest_changed_on_disk_is_rejected_before_any_network(fetcher, tmp_path):
    path = tmp_path / "manifest.json"
    path.write_bytes(fetcher.MANIFEST.read_bytes() + b" ")
    with pytest.raises(fetcher.RuleFetchError, match="pinned SHA-256"):
        fetcher.load_manifest(path)


def test_manifest_symlink_is_rejected(fetcher, tmp_path):
    path = tmp_path / "manifest.json"
    path.symlink_to(fetcher.MANIFEST)
    with pytest.raises(fetcher.RuleFetchError, match="regular local"):
        fetcher.load_manifest(path)


@pytest.mark.parametrize("change", ["host", "http", "moving_ref", "credentials", "query", "traversal",
                                    "duplicate", "missing", "hash", "commit", "repository"])
def test_unapproved_manifest_variants_are_rejected(fetcher, synthetic, change):
    manifest = copy.deepcopy(synthetic[0])
    entry = manifest["files"][0]
    if change == "host":
        entry["url"] = entry["url"].replace("raw.githubusercontent.com", "elsewhere.invalid")
    elif change == "http":
        entry["url"] = entry["url"].replace("https://", "http://")
    elif change == "moving_ref":
        entry["url"] = entry["url"].replace(fetcher.COMMIT, "main")
    elif change == "credentials":
        entry["url"] = entry["url"].replace("https://", "https://user:synthetic@")
    elif change == "query":
        entry["url"] += "?alternate=1"
    elif change == "traversal":
        entry["path"] = "../outside.yml"
    elif change == "duplicate":
        manifest["files"][1] = copy.deepcopy(entry)
    elif change == "missing":
        manifest["files"].pop()
    elif change == "hash":
        entry["sha256"] = "invalid"
    elif change == "commit":
        manifest["commit"] = "0" * 40
    elif change == "repository":
        manifest["repository"] = "https://github.com/elsewhere/rules"
    with pytest.raises(fetcher.RuleFetchError):
        fetcher.validate_manifest(manifest)


def test_fetch_uses_verified_https_without_auth_and_reuses_exact_cache(fetcher, synthetic, monkeypatch, tmp_path):
    manifest, bodies = synthetic
    calls, handlers, responses = mock_network(fetcher, monkeypatch, bodies)
    destination = tmp_path / "references"
    result = fetcher.fetch_rules(manifest, destination)
    assert result["verified_rule_count"] == result["downloaded_rule_count"] == 12
    assert len(calls) == 12
    assert all(request.get_method() == "GET" and request.full_url.startswith(fetcher.RAW_PREFIX)
               and request.headers == {"Accept": "text/plain"} and timeout == fetcher.NETWORK_TIMEOUT
               for request, timeout in calls)
    assert all(response.read_limits == [fetcher.MAX_RULE_BYTES + 1] for response in responses)
    https = [handler for handler in handlers if isinstance(handler, fetcher.urllib.request.HTTPSHandler)]
    assert all(handler._context.verify_mode == ssl.CERT_REQUIRED and handler._context.check_hostname
               for handler in https)
    proxies = [handler for handler in handlers if isinstance(handler, fetcher.urllib.request.ProxyHandler)]
    assert all(handler.proxies == {} for handler in proxies)
    assert fetcher.verify_rules_directory(manifest, destination) == {
        entry["path"]: entry["sha256"] for entry in manifest["files"]}
    result = fetcher.fetch_rules(manifest, destination)
    assert result["downloaded_rule_count"] == 0 and len(calls) == 12
    assert not list(destination.rglob(".rule-*"))


def test_bad_download_hash_writes_no_rule(fetcher, synthetic, monkeypatch, tmp_path):
    manifest, bodies = synthetic
    bodies = dict(bodies)
    bodies[manifest["files"][-1]["path"]] = b"changed synthetic rule"
    mock_network(fetcher, monkeypatch, bodies)
    destination = tmp_path / "references"
    with pytest.raises(fetcher.RuleFetchError, match="Downloaded rule differs"):
        fetcher.fetch_rules(manifest, destination)
    assert not destination.exists()


@pytest.mark.parametrize("failure", ["redirected_url", "bad_status", "large_header", "invalid_header", "large_body"])
def test_untrusted_http_response_is_rejected(fetcher, synthetic, monkeypatch, failure):
    manifest, bodies = synthetic
    entry = manifest["files"][0]

    def change(path, response):
        if failure == "redirected_url":
            response.url = "https://elsewhere.invalid/rule.yml"
        elif failure == "bad_status":
            response.status = 302
        elif failure == "large_header":
            response.headers = {"Content-Length": str(fetcher.MAX_RULE_BYTES + 1)}
        elif failure == "invalid_header":
            response.headers = {"Content-Length": "invalid"}
        elif failure == "large_body":
            response.seek(0)
            response.write(b"x" * (fetcher.MAX_RULE_BYTES + 1))
            response.seek(0)

    mock_network(fetcher, monkeypatch, bodies, change)
    with pytest.raises(fetcher.RuleFetchError):
        fetcher._download(entry)


def test_redirect_handler_refuses_following_redirects(fetcher):
    with pytest.raises(fetcher.RuleFetchError, match="redirects are forbidden"):
        fetcher._NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.invalid/")


@pytest.mark.parametrize("conflict", ["changed_rule", "unexpected_file", "symlink_file", "symlink_directory"])
def test_existing_conflicting_cache_is_not_overwritten_or_fetched(fetcher, synthetic, monkeypatch, tmp_path, conflict):
    manifest, bodies = synthetic
    destination = tmp_path / "references"
    destination.mkdir()
    path = destination / manifest["files"][0]["path"]
    path.parent.mkdir(parents=True)
    if conflict == "changed_rule":
        path.write_bytes(b"tampered synthetic rule")
    elif conflict == "unexpected_file":
        (destination / "unexpected.yml").write_bytes(b"unexpected")
    elif conflict == "symlink_file":
        path.symlink_to(tmp_path / "external")
    elif conflict == "symlink_directory":
        (destination / "linked").symlink_to(tmp_path, target_is_directory=True)
    calls, _, _ = mock_network(fetcher, monkeypatch, bodies)
    with pytest.raises(fetcher.RuleFetchError):
        fetcher.fetch_rules(manifest, destination)
    assert not calls
    if conflict == "changed_rule":
        assert path.read_bytes() == b"tampered synthetic rule"


def test_complete_verification_rejects_missing_rules(fetcher, synthetic, tmp_path):
    with pytest.raises(fetcher.RuleFetchError, match="incomplete"):
        fetcher.verify_rules_directory(synthetic[0], tmp_path / "missing")


def test_atomic_write_refuses_concurrent_conflicting_entry_and_cleans_temporary(fetcher, tmp_path, monkeypatch):
    destination = tmp_path / "rule.yml"
    real_link = fetcher.os.link

    def conflicting_link(source, target):
        target.write_bytes(b"concurrent synthetic change")
        return real_link(source, target)

    monkeypatch.setattr(fetcher.os, "link", conflicting_link)
    with pytest.raises(fetcher.RuleFetchError, match="changed while writing"):
        fetcher._atomic_write(destination, b"approved synthetic rule")
    assert destination.read_bytes() == b"concurrent synthetic change"
    assert not list(tmp_path.glob(".rule-*"))
