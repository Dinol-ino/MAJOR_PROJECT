"""Check that DFrag can actually reach its configured PostgreSQL.

Run from the project root with the backend venv's interpreter:

    backend\\venv\\Scripts\\python.exe check_db.py

Tests both paths the app uses:
  * native  - the DATABASE_URL in backend/.env, over loopback
  * docker  - the URL compose builds from DFRAG_PG_* in the root .env

Reports the real failure (refused / auth / missing database) instead of a
stack trace, and never prints the password.
"""

from __future__ import annotations

import os
import re
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
OK, BAD, WARN = "  [ OK ]", "  [FAIL]", "  [WARN]"


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def redact(url: str) -> str:
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url)


def tcp_open(host: str, port: int, timeout: float = 4.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def check(label: str, url: str) -> bool:
    print(f"\n{label}")
    print(f"  url   {redact(url)}")

    parts = urlsplit(url)
    host, port = parts.hostname or "", parts.port or 5432
    dbname = (parts.path or "").lstrip("/")

    reachable, why = tcp_open(host, port)
    if not reachable:
        print(f"{BAD} TCP {host}:{port} unreachable - {why}")
        if host in ("host.docker.internal",):
            print("       Expected from the host: that name only resolves inside a container.")
            print("       Docker will still resolve it via the backend's extra_hosts mapping.")
        else:
            print("       PostgreSQL is not listening there, or a firewall is blocking it.")
        return False
    print(f"{OK} TCP {host}:{port} reachable")

    try:
        import psycopg
    except Exception as exc:
        print(f"{BAD} cannot import psycopg - {type(exc).__name__}: {exc}")
        if "pq wrapper" in str(exc) or "libpq" in str(exc).lower():
            print("       psycopg 3 needs a libpq implementation, which plain `psycopg`")
            print("       does not ship. Install the binary build:")
            print("         backend\\venv\\Scripts\\python.exe -m pip install \"psycopg[binary]\"")
        else:
            print("       Run this with backend\\venv\\Scripts\\python.exe")
        print("       (TCP reachability above is still valid; auth was not tested.)")
        return False

    # psycopg speaks plain libpq URLs; strip SQLAlchemy's driver suffix.
    libpq = url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(libpq, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_database(), current_user")
                ver, db, user = cur.fetchone()
                cur.execute(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
                (tables,) = cur.fetchone()
        print(f"{OK} authenticated as {user!r} on database {db!r}")
        print(f"       {ver.split(',')[0]}")
        if tables:
            print(f"{OK} {tables} table(s) in public schema - schema already initialised")
        else:
            print(f"{WARN} 0 tables in public schema - the backend will create them on first start")
        return True
    except Exception as exc:
        msg = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        print(f"{BAD} {msg}")
        low = msg.lower()
        if "does not exist" in low and dbname and dbname in msg:
            print(f"       Create it:  CREATE DATABASE {dbname};")
        elif "password authentication failed" in low:
            print("       Wrong password for this user - fix DATABASE_URL / DFRAG_PG_PASSWORD.")
        elif "no pg_hba.conf entry" in low:
            print("       Server reachable but refusing this client address.")
            print("       Add a pg_hba.conf line covering it, then reload PostgreSQL.")
        return False


def main() -> int:
    print("DFrag database connectivity check")

    native = read_env(ROOT / "backend" / ".env").get("DATABASE_URL", "").strip()
    root = read_env(ROOT / ".env")

    results: list[tuple[str, bool]] = []

    if native:
        results.append(("native (uvicorn)", check("native (uvicorn) - backend/.env", native)))
    else:
        print("\nnative (uvicorn) - backend/.env\n  DATABASE_URL empty: the app would use local SQLite.")

    host = root.get("DFRAG_PG_HOST", "postgres")
    docker_url = (
        f"postgresql://{root.get('DFRAG_PG_USER', 'postgres')}:"
        f"{root.get('DFRAG_PG_PASSWORD', '')}@{host}:"
        f"{root.get('DFRAG_PG_PORT', '5432')}/{root.get('DFRAG_PG_DB', 'dfrag')}"
    )

    if host in ("host.docker.internal", "postgres"):
        # Probe the same server the container will reach, via loopback.
        probe = docker_url.replace(f"@{host}:", "@127.0.0.1:", 1)
        print("\ndocker (compose) - root .env")
        print(f"  container url   {redact(docker_url)}")
        print(f"  probing the same server over loopback instead, since {host!r}")
        print("  only resolves inside the container:")
        results.append(("docker (compose)", check("  -> loopback equivalent", probe)))
    else:
        results.append(("docker (compose)", check("docker (compose) - root .env", docker_url)))

    print("\n" + "-" * 60)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results if not ok]
    if failed:
        print("\nNot ready. Fix the FAIL above before `docker compose up`.")
        return 1
    print("\nBoth paths reach the database. Safe to build.")
    print("Note: a container connects from the Docker NAT subnet, not loopback, so")
    print("postgresql.conf listen_addresses and pg_hba.conf must allow that range.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
