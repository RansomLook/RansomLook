#!/usr/bin/env python3
"""Scan BitTorrent swarms referenced by posts in DB_POSTS.

One pass over every magnet, adaptive interval per infohash
(alive / dead / frozen), peer samples stored in DB_TORRENT_HEALTH with a
30-day TTL. Designed to run from cron, e.g.::

    0 */6 * * *  cd /opt/ransomlook/RansomLook && poetry run torrent-health

A specific infohash can be forced from the CLI via ``--only``, which bypasses
the interval check (used by the live refresh endpoint).
"""

import argparse
import logging
import sys

from ransomlook import torrent_health
from ransomlook.default.logging import get_logger

logger = get_logger("torrent_health")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", action="append", help="Infohash to scan (repeatable). Bypasses interval check.")
    ap.add_argument("--group", action="append",
                    help="Ransomware group name (case-insensitive). Expands to every infohash "
                         "currently associated with that group. Repeatable, bypasses interval check.")
    ap.add_argument("--magnet", action="append",
                    help="Ad-hoc magnet URI to scan, outside the DB_POSTS scope. Result is still persisted in "
                         "DB_TORRENT_HEALTH; group/post linkage will be empty. Repeatable.")
    ap.add_argument("--scan-duration", type=int, default=torrent_health.DEFAULT_SCAN_DURATION,
                    help="Seconds to stay in each swarm (default: %(default)s)")
    ap.add_argument("--batch-size", type=int, default=torrent_health.DEFAULT_BATCH_SIZE,
                    help="Magnets scanned concurrently per batch (default: %(default)s)")
    ap.add_argument("--alive-interval", type=int, default=torrent_health.DEFAULT_ALIVE_INTERVAL,
                    help="Min seconds between scans for alive swarms (default: %(default)s)")
    ap.add_argument("--dead-interval", type=int, default=torrent_health.DEFAULT_DEAD_INTERVAL,
                    help="Min seconds between scans for recently-dead swarms (default: %(default)s)")
    ap.add_argument("--frozen-interval", type=int, default=torrent_health.DEFAULT_FROZEN_INTERVAL,
                    help="Min seconds between scans for swarms dead >7d (default: %(default)s)")
    ap.add_argument("--max-infohashes", type=int, default=None,
                    help="Cap at N infohashes this run (debug / rate-limit)")
    ap.add_argument("--listen-port", type=int, default=6881,
                    help="libtorrent listen port (default: %(default)s)")
    ap.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None)
    args = ap.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    if args.magnet:
        # Ad-hoc path: scan arbitrary magnets, persist without post linkage.
        sess = torrent_health.build_session(listen_port=args.listen_port)
        import time
        time.sleep(3)  # DHT bootstrap
        ok = failed = 0
        for start in range(0, len(args.magnet), args.batch_size):
            batch = args.magnet[start:start + args.batch_size]
            try:
                results = torrent_health.scan_batch(sess, batch, duration=args.scan_duration)
            except Exception as e:
                logger.warning("batch failed: %s", e)
                failed += len(batch)
                continue
            for i, result in enumerate(results):
                magnet = batch[i] if i < len(batch) else batch[-1]
                torrent_health.store_scan(result, [magnet], groups=[])
                logger.info(
                    "scanned %s: %d peers (%d seed / %d leech)",
                    result.infohash, result.peers_count, result.seeders, result.leechers,
                )
                ok += 1
            failed += len(batch) - len(results)
        logger.info("done: scanned=%d failed=%d", ok, failed)
        sys.exit(0 if failed == 0 else 1)

    # ── Resolve --group → list of infohashes, merge with --only ─────────
    only = list(args.only or [])
    if args.group:
        wanted = {g.lower().strip() for g in args.group if g and g.strip()}
        targets = torrent_health.collect_magnets()
        matched = [
            ih for ih, data in targets.items()
            if any(g.lower() in wanted for g in data.get("groups") or [])
        ]
        if not matched:
            logger.warning("no infohash found for group(s): %s", ", ".join(sorted(wanted)))
        else:
            logger.info("--group %s → %d infohash(es)", ", ".join(sorted(wanted)), len(matched))
            only.extend(matched)

    stats = torrent_health.run_once(
        only=only if only else None,
        scan_duration=args.scan_duration,
        batch_size=args.batch_size,
        alive_interval=args.alive_interval,
        dead_interval=args.dead_interval,
        frozen_interval=args.frozen_interval,
        max_infohashes=args.max_infohashes,
        listen_port=args.listen_port,
    )
    logger.info("done: %s", stats)
    sys.exit(0 if stats["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
