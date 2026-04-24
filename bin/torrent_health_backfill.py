#!/usr/bin/env python3
"""Rescan infohashes that are missing static metadata (name / trackers / files).

Torrents added from a magnet URI without ``ws=`` or with minimal ``tr=``
rely on libtorrent's ``ut_metadata`` extension (BEP 9) to fetch the info
dict from a willing peer. Under the default ``scan-duration`` (45 s) that
exchange often doesn't complete, so the meta row ends up with peers but
no name / size / files / trackers.

This tool enumerates those incomplete rows and rescans them with a
longer window (default 300 s) so the metadata can land. Safe to run
on-demand or from a daily cron — the list is recomputed each run, so
already-populated rows are skipped automatically.

Typical usage::

    # One-shot, default filters (name or trackers missing, with live peers)
    poetry run torrent-health-backfill

    # Include torrents even without live peers (slower, less useful)
    poetry run torrent-health-backfill --all

    # Also fill missing file lists when present
    poetry run torrent-health-backfill --include-files

    # Cap for test / rate control
    poetry run torrent-health-backfill --max 50

    # Longer scan window per swarm (600 s) for stubborn cases
    poetry run torrent-health-backfill --scan-duration 600

    # See what would be scanned, don't actually scan
    poetry run torrent-health-backfill --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from ransomlook import torrent_health
from ransomlook.default.logging import get_logger

logger = get_logger("torrent_health_backfill")


def _needs_backfill(meta: dict[str, Any], *, include_files: bool) -> tuple[bool, list[str]]:
    """Return (needs, reasons) — ``reasons`` is human-readable list for logs."""
    reasons: list[str] = []
    name = (meta.get("name") or "").strip()
    if not name:
        reasons.append("no name")
    trackers = meta.get("trackers") or []
    if not trackers:
        reasons.append("no trackers")
    if include_files and not (meta.get("files") or []):
        reasons.append("no files")
    return bool(reasons), reasons


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--scan-duration", type=int, default=300,
                    help="Seconds per swarm — higher = more chance for "
                         "ut_metadata to complete (default: 300).")
    ap.add_argument("--batch-size", type=int,
                    default=torrent_health.DEFAULT_BATCH_SIZE,
                    help="Magnets scanned concurrently per batch "
                         "(default: %(default)s).")
    ap.add_argument("--max", type=int, default=None,
                    help="Cap at N infohashes this run (default: all).")
    ap.add_argument("--all", action="store_true",
                    help="Include infohashes with 0 peers too (default: "
                         "only those with last_peers_count > 0).")
    ap.add_argument("--include-files", action="store_true",
                    help="Also backfill rows whose files list is empty — "
                         "some torrents legitimately have no `files` (single-"
                         "file torrents are represented differently), so off "
                         "by default.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print candidates and exit without scanning.")
    ap.add_argument("--listen-port", type=int, default=6881)
    ap.add_argument("--log-level",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    default=None)
    args = ap.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    # ── Find infohashes needing metadata ────────────────────────────────
    missing: list[tuple[str, list[str]]] = []
    total = 0
    for ih in torrent_health.list_infohashes():
        total += 1
        meta = torrent_health.get_meta(ih) or {}
        needs, reasons = _needs_backfill(meta, include_files=args.include_files)
        if not needs:
            continue
        if not args.all and (meta.get("last_peers_count") or 0) <= 0:
            continue  # dead swarm — backfill unlikely to help, skip
        missing.append((ih, reasons))

    if args.max is not None:
        missing = missing[: args.max]

    logger.info("total meta rows: %d · needing backfill: %d", total, len(missing))
    if not missing:
        logger.info("nothing to do.")
        return 0

    if args.dry_run:
        for ih, reasons in missing[:30]:
            print(f"{ih}  [{', '.join(reasons)}]")
        if len(missing) > 30:
            print(f"… and {len(missing) - 30} more")
        return 0

    # ── Rescan them with a longer window ─────────────────────────────────
    only = [ih for ih, _ in missing]
    stats = torrent_health.run_once(
        only=only,
        scan_duration=args.scan_duration,
        batch_size=args.batch_size,
        alive_interval=0,       # bypass adaptive scheduling entirely
        dead_interval=0,
        frozen_interval=0,
        max_infohashes=None,
        listen_port=args.listen_port,
    )
    logger.info("done: %s", stats)

    # ── Post-scan verdict: count how many now have metadata ──────────────
    recovered = 0
    for ih, _ in missing:
        meta = torrent_health.get_meta(ih) or {}
        if (meta.get("name") or "").strip() and (meta.get("trackers") or []):
            recovered += 1
    logger.info("metadata recovered: %d / %d (%.1f%%)",
                recovered, len(missing),
                (recovered / len(missing) * 100) if missing else 0.0)

    return 0 if stats.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
