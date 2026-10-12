"""Focused credential-pattern scan. Reports locations only, never matched values.

This is not an exhaustive credential detection or independent security audit.
Scan Git revisions too so removing a credential from HEAD cannot hide history.
"""
import argparse
import json
import re
import subprocess

PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "highlevel_private_token": re.compile(r"\bpit-[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I),
}


def scan(revision):
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", revision], text=True).splitlines()
    findings = []
    for name in names:
        data = subprocess.check_output(["git", "show", revision + ":" + name])
        try: content = data.decode("utf-8")
        except UnicodeDecodeError: continue
        for number, line in enumerate(content.splitlines(), 1):
            for rule, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append({"revision": revision, "file": name, "line": number, "rule": rule})
    return {"revision": revision, "files_scanned": len(names), "findings": findings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("revisions", nargs="+", help="Explicit Git revisions to inspect")
    results = [scan(revision) for revision in parser.parse_args().revisions]
    print(json.dumps({"scanner": "focused credential patterns; no exhaustive claim", "results": results}, indent=2))
    raise SystemExit(int(any(result["findings"] for result in results)))
