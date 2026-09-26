"""Inspect a portable ZIP for accidental project data and embedded build-host paths."""
from __future__ import annotations

import re
import sys
import zipfile
import getpass
from pathlib import Path

FORBIDDEN_NAMES = re.compile(r"(?:^|/)(?:project\.sqlite3(?:-\w+)?|project\.json|config\.json|app\.log|.*\.lmw|.*\.dmp)$", re.I)
BUILD_PATH = re.compile(rb"[A-Za-z]:[\\/]{1,2}(?:Users|Documents)[\\/]", re.I)
SECRET = re.compile(rb"(?:sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{80,}-----END)")


def audit(path: Path) -> list[str]:
    findings = []
    host_user = getpass.getuser().encode("utf-8").lower()
    upstream_paths = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts:
                findings.append(f"{name}: unsafe archive path")
            if FORBIDDEN_NAMES.search(name) or "/logs/" in name.lower() or "/cache/" in name.lower():
                findings.append(f"{name}: project/config/log/cache payload")
            if info.is_dir():
                continue
            with archive.open(info) as member:
                overlap = b""
                while chunk := member.read(1024 * 1024):
                    data = overlap + chunk
                    for match in BUILD_PATH.finditer(data):
                        segment = data[match.start():match.start() + 220].lower()
                        if host_user and host_user in segment:
                            findings.append(f"{name}: embedded build-host user path")
                            break
                        upstream_paths += 1
                    if findings and findings[-1].startswith(f"{name}: embedded build-host"):
                        break
                    if SECRET.search(data):
                        findings.append(f"{name}: possible secret")
                        break
                    overlap = data[-128:]
    print("Upstream binary build-path markers (informational):", upstream_paths)
    return findings


if __name__ == "__main__":
    target = Path(sys.argv[1])
    results = audit(target)
    print("Portable ZIP audit:", "PASS" if not results else "REVIEW REQUIRED")
    print("Findings:", len(results))
    for result in results:
        print(result)
    raise SystemExit(bool(results))
