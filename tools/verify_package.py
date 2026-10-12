"""Verify built artifacts, including documents needed for source installation."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile


def verify(directory):
    directory = Path(directory)
    wheels = sorted(directory.glob("*.whl"))
    sdists = sorted(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Build into a fresh directory containing exactly one wheel and one sdist.")
    required_app = {
        "ultimatesales_connector/modules.txt", "ultimatesales_connector/patches.txt",
        "ultimatesales_connector/setup.py", "ultimatesales_connector/hooks.py",
        "ultimatesales_connector/tests/test_install_contract.py",
        "ultimatesales_connector/tests/test_native_queue.py",
        "ultimatesales_connector/tests/test_permissions_recovery.py",
        "ultimatesales_connector/ultimatesales_connector/workspace/ultimatesales_connector/ultimatesales_connector.json",
    }
    for name in ("us_connection", "us_record_link", "us_sync_job"):
        base = f"ultimatesales_connector/ultimatesales_connector/doctype/{name}/{name}"
        required_app.update({base + ".py", base + ".json"})
        if name != "us_record_link": required_app.add(base + ".js")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
        if required_app - names:
            raise ValueError("Wheel missing required app files: " + str(sorted(required_app - names)))
        for name in names:
            if name.endswith(".json"):
                json.loads(archive.read(name))
        if any(".reference-source" in name or name.startswith(("docs/upstream/raw/", "docs/upstream/marketplace/")) for name in names):
            raise ValueError("Downloaded reference sources must not be included in the wheel.")
    with tarfile.open(sdists[0]) as archive:
        names = {name.split("/", 1)[1] for name in archive.getnames() if "/" in name}
        required_source = required_app | {
            "pyproject.toml", "LICENSE", "AGENTS.md", "README.md", "SECURITY.md",
            "docs/INSTALLATION.md", "docs/CONFIGURATION.md", "docs/RECOVERY.md",
            "docs/ENVIRONMENT_MATRIX.md", "docs/STEP_1_TO_4_REPORT.md", "docs/TEST_EVIDENCE.md",
            "tooling/environments/versions.env", "tooling/environments/bench-acceptance.sh", "tools/run_acceptance.py",
            ".github/workflows/offline-tests.yml", ".github/workflows/installed-site.yml",
            "docs/upstream/security-rules-manifest.json", "tools/fetch_security_rules.py",
            "tooling/environments/scan-security.py",
        }
        if required_source - names:
            raise ValueError("Source distribution missing required files: " + str(sorted(required_source - names)))
        if any(".reference-source" in name or name.startswith(("docs/upstream/raw/", "docs/upstream/marketplace/")) for name in names):
            raise ValueError("Downloaded reference sources must not be included in the source distribution.")
    return [{"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in (wheels[0], sdists[0])]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    print(json.dumps({"status": "PASS", "artifacts": verify(parser.parse_args().directory)}, indent=2))
