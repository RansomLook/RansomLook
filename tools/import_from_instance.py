#!/usr/bin/env python3
"""Import data from a remote RansomLook instance via /api/export/<db>."""

import argparse
import json
import os
import sys

import requests
import valkey

from ransomlook.default import DB_ACTORS, DB_GROUPS, DB_LEAKS, DB_MARKETS, DB_POSTS, DB_RF, get_socket_path
from ransomlook.default.logging import get_logger

logger = get_logger("import_from_instance")

# DB number → (label, Redis DB)
DATABASES = {
    "0": ("Groups", DB_GROUPS),
    "2": ("Posts", DB_POSTS),
    "3": ("Markets", DB_MARKETS),
    "4": ("Leaks", DB_LEAKS),
    "5": ("Actors", DB_ACTORS),
    "10": ("Recorded Future", DB_RF),
}

DEFAULT_URL = "https://www.ransomlook.io/api"


def _import_db(session: requests.Session, base_url: str, db_num: str, label: str, redis_db: int) -> None:
    url = f"{base_url}/export/{db_num}"
    logger.info(f"  [{db_num:>2}] {label} …")

    resp = session.get(url, timeout=120)
    if resp.status_code == 401:
        logger.error("DENIED (invalid or missing API key)")
        return
    if resp.status_code == 403:
        logger.error(f"FORBIDDEN (DB {db_num} not allowed for export)")
        return
    if resp.status_code != 200:
        logger.error(f"ERROR (HTTP {resp.status_code})")
        return

    data = resp.json()
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=redis_db)
    count = 0
    for key, value in data.items():
        red.set(key, json.dumps(value))
        count += 1
    logger.info(f"{count} keys")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import data from a remote RansomLook instance.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Remote API base URL (default: {DEFAULT_URL})")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("RANSOMLOOK_API_KEY", ""),
        help="API key (or set RANSOMLOOK_API_KEY env var)",
    )
    parser.add_argument("--db", nargs="*", choices=list(DATABASES.keys()), help="Import only these DBs (default: all)")
    args = parser.parse_args()

    if not args.api_key:
        logger.error("Error: API key required. Use --api-key or set RANSOMLOOK_API_KEY.")
        sys.exit(1)

    base_url = args.url.rstrip("/")
    dbs = args.db if args.db else list(DATABASES.keys())

    session = requests.Session()
    session.headers["Authorization"] = args.api_key

    logger.info(f"Importing from {base_url}")
    logger.info(f"Databases: {', '.join(dbs)}")

    for db_num in dbs:
        label, redis_db = DATABASES[db_num]
        _import_db(session, base_url, db_num, label, redis_db)

    logger.info("Done.")


if __name__ == "__main__":
    main()
