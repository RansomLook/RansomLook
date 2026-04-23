#!/usr/bin/env python3
"""Replace corrupted magnet / tracker / webseed fields on existing meta rows.

Workflow:

1. Read a newline-separated file of clean magnet URIs (produced by the
   fixed Akira browser scraper, for example).
2. For each magnet, parse it via libtorrent to obtain infohash + fresh
   trackers / webseeds.
3. If a ``torrent_health:meta:<ih>`` already exists, **replace** its
   ``magnets`` / ``trackers`` / ``webseeds`` fields with the clean values
   (no merge — merging keeps the corrupted entries).
4. Also strip embedded ``\n`` from ``name`` and ``comment`` while we're
   at it.

Unlike ``add_group_torrent.py`` which merges and preserves prior state,
this tool is destructive on those three fields — use when you know the
current values are garbage and want a clean reset.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from ransomlook import torrent_health as th
from ransomlook.torrent_health import _redis

logger = logging.getLogger(__name__)


def _clean_text(val: str) -> str:
    return re.sub(r"[\r\n]+", "", val).strip()


def replace(magnets_file: Path, dry_run: bool = True) -> dict[str, int]:
    r = _redis()
    stats = {
        "read": 0, "parsed": 0, "parse_failed": 0,
        "no_existing": 0, "updated": 0,
        "name_fixed": 0, "comment_fixed": 0,
    }

    for raw_line in magnets_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        stats["read"] += 1

        try:
            info = th.parse_magnet_or_torrent(line)
        except Exception as e:
            stats["parse_failed"] += 1
            logger.warning("parse failed: %s (%s)", line[:80], e)
            continue
        stats["parsed"] += 1

        ih = info["infohash"]
        meta_key = f"torrent_health:meta:{ih}"
        existing: dict[bytes, bytes] = r.hgetall(meta_key)  # type: ignore[assignment]
        if not existing:
            stats["no_existing"] += 1
            logger.info("%s: no existing meta, skipped (use add_group_torrent to register new)", ih)
            continue

        updates: dict[str, str] = {"magnets": json.dumps([info["magnet"]])}

        md = info.get("metadata") or {}
        if md.get("trackers"):
            updates["trackers"] = json.dumps(sorted(set(md["trackers"])))
        if md.get("webseeds"):
            updates["webseeds"] = json.dumps(sorted(set(md["webseeds"])))

        # Clean text fields while we're here.
        for field in ("name", "comment"):
            old = existing.get(field.encode(), b"").decode()
            if not old:
                continue
            new = _clean_text(old)
            if new != old:
                updates[field] = new
                stats[f"{field}_fixed"] += 1

        stats["updated"] += 1
        logger.info("%s: replace magnets=%d trackers=%d webseeds=%d",
                    ih, 1, len(md.get("trackers") or []), len(md.get("webseeds") or []))
        if not dry_run:
            r.hset(meta_key, mapping=updates)

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path,
                    help="Newline-separated file of clean magnet URIs.")
    ap.add_argument("--apply", action="store_true",
                    help="Actually persist the changes (default: dry-run).")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not args.file.is_file():
        print(f"error: {args.file} not found", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )

    stats = replace(args.file, dry_run=not args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"--- {mode} ---")
    for k, v in stats.items():
        print(f"{k:>18}: {v}")
    if not args.apply:
        print("\nRe-run with --apply to persist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
