#!/usr/bin/env python3
"""Fail CI when obviously sensitive files or tokens are tracked."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PATHS = {
    ".env",
    ".env.local",
    ".env.production",
}
FORBIDDEN_SUFFIXES = (".pem", ".p12", ".key")
SECRET_PATTERNS = {
    "openrouter_key": re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{20,}\b"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
PLACEHOLDER_SNIPPETS = (
    "postgresql://user:pass@",
    "OPENROUTER_API_KEY=",
    "TELEGRAM_BOT_TOKEN=",
    "TELEGRAM_CHAT_ID=",
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def is_forbidden_path(path: Path) -> bool:
    name = path.name.lower()
    return str(path) in FORBIDDEN_PATHS or name.endswith(FORBIDDEN_SUFFIXES)


def main() -> int:
    problems: list[str] = []
    for path in tracked_files():
        if is_forbidden_path(path):
            problems.append(f"tracked sensitive path: {path}")
            continue
        if path.parts and path.parts[0] == "dev_documents":
            problems.append(f"private docs directory should stay untracked: {path}")
            continue
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(snippet in content for snippet in PLACEHOLDER_SNIPPETS):
            content_for_scan = content
        else:
            content_for_scan = content
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content_for_scan):
                problems.append(f"{path}: matched {label}")

    if problems:
        print("Repo hygiene check failed:", file=sys.stderr)
        for problem in problems:
            print(f" - {problem}", file=sys.stderr)
        return 1

    print("Repo hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
