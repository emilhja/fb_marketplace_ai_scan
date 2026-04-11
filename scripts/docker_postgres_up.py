#!/usr/bin/env python3
"""Start a local Postgres in Docker for AIMM cache; update AIMM_DATABASE_URL in .env.

Uses credentials and DB name from AIMM_DATABASE_URL. Publishes on host port 55432
by default to avoid clashing with a system Postgres on 5432.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def docker(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--publish-port",
        type=int,
        default=55432,
        help="Host TCP port mapped to Postgres 5432 inside the container.",
    )
    p.add_argument(
        "--container-name",
        default="facebook_marketplace_scan_pg",
        help="Docker container name.",
    )
    p.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parent.parent / ".env",
        help="Path to .env containing AIMM_DATABASE_URL.",
    )
    args = p.parse_args()

    env_path = args.env_file
    text = env_path.read_text(encoding="utf-8")
    m = re.search(r"^(AIMM_DATABASE_URL=)(.+)$", text, re.MULTILINE)
    if not m:
        print("AIMM_DATABASE_URL not found in .env", file=sys.stderr)
        return 1
    prefix, raw = m.group(1), m.group(2).strip().strip('"').strip("'")
    if raw.startswith("postgresql+asyncpg://"):
        raw = "postgresql://" + raw.split("postgresql+asyncpg://", 1)[1]
    parsed = urlparse(raw)
    user = parsed.username or "postgres"
    password = parsed.password or ""
    db = (parsed.path or "").lstrip("/").split("/")[0] or "marketplace_scan"
    if not password:
        print("AIMM_DATABASE_URL must include a password.", file=sys.stderr)
        return 1

    name = args.container_name
    publish_port = args.publish_port

    inspect = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True,
        text=True,
    )
    if inspect.returncode == 0:
        if inspect.stdout.strip() == "true":
            print(f"Container {name} already running.")
        else:
            print(f"Starting existing container {name}...")
            docker(["start", name])
    else:
        print(f"Creating container {name} (host port {publish_port} -> 5432)...")
        docker(
            [
                "run",
                "-d",
                "--name",
                name,
                "-p",
                f"{publish_port}:5432",
                "-e",
                f"POSTGRES_USER={user}",
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-e",
                f"POSTGRES_DB={db}",
                "postgres:16-alpine",
            ]
        )

    for _ in range(60):
        r = subprocess.run(
            ["docker", "exec", name, "pg_isready", "-U", user, "-d", db],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            print("PostgreSQL is ready.")
            break
        time.sleep(1)
    else:
        print("Timeout waiting for PostgreSQL.", file=sys.stderr)
        return 1

    netloc = f"{user}:{password}@127.0.0.1:{publish_port}"
    new_url = urlunparse(parsed._replace(netloc=netloc, path=f"/{db}"))
    new_text = text[: m.start()] + prefix + new_url + text[m.end() :]
    env_path.write_text(new_text, encoding="utf-8")
    print(f"Updated {env_path} → AIMM_DATABASE_URL now uses 127.0.0.1:{publish_port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
