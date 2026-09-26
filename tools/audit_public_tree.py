"""Conservative pre-publication scan of source candidates; never prints secret values."""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".venv", "venv", "build", "dist", "dev_data", "__pycache__",
            ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode"}
PRIVATE_SUFFIXES = {".lmw", ".sqlite3", ".onnx", ".pdmodel", ".pdiparams",
                    ".ttf", ".otf", ".ttc", ".pdf", ".log", ".dmp", ".mdmp", ".zip",
                    ".db", ".bin", ".model", ".stackdump"}
TEXT_SUFFIXES = {".py", ".ps1", ".md", ".json", ".toml", ".txt", ".yml", ".yaml"}
PATTERNS = {
    "windows_user_path": re.compile(r"[A-Za-z]:[\\/]{1,2}(?:Users|Documents)[\\/]", re.I),
    "api_token": re.compile(r"(?:sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,}|AKIA[0-9A-Z]{16})"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "personal_email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "chinese_phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "credential_literal": re.compile(r"(?:password|cookie|api_key|access_token|refresh_token)\s*[:=]\s*['\"][A-Za-z0-9+/=_-]{12,}['\"]", re.I),
    "bearer_literal": re.compile(r"Bearer\s+[A-Za-z0-9_.-]{20,}", re.I),
    "private_ipv4": re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
}


def scan() -> list[str]:
    findings = []
    for directory, subdirs, filenames in os.walk(ROOT):
        subdirs[:] = [name for name in subdirs if name not in EXCLUDED]
        for name in filenames:
            path = Path(directory) / name
            relative = path.relative_to(ROOT)
            if path.suffix.lower() in PRIVATE_SUFFIXES or name in {"project.json", "config.json"}:
                findings.append(f"{relative}: forbidden source asset")
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES and name not in {".gitignore", "requirements.txt"}:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                findings.append(f"{relative}: unreadable text")
                continue
            for number, line in enumerate(lines, 1):
                for label, pattern in PATTERNS.items():
                    if pattern.search(line):
                        findings.append(f"{relative}:{number}: {label}")
    return findings


if __name__ == "__main__":
    results = scan()
    print("Public source candidate scan:", "PASS" if not results else "REVIEW REQUIRED")
    print("Findings:", len(results))
    for result in results:
        print(result)
    raise SystemExit(bool(results))
