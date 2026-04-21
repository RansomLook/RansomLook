#!/usr/bin/env python3
"""Proactively enrich every peer IP observed in torrent-health scans.

Walks ``torrent_health:scan:*`` entries in DB_TORRENT_HEALTH, collects unique
peer IPs and enriches the ones not currently cached (or all of them with
``--force``). Runs sequentially against CIRCL IP ASN History with a short
HTTP timeout; polite by design.

Recommended cron placement::

    30 3 * * * cd /opt/ransomlook/RansomLook && flock -n /tmp/rl-enrich.lock \
        poetry run enrich-ips >> logs/enrich_ips.log 2>&1
"""

import argparse
import logging
import sys
import time

from ransomlook import ipenrich
from ransomlook.default.logging import get_logger

logger = get_logger("enrich_ips")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="Re-enrich every IP even if still cached (bypass 7-day cache).")
    ap.add_argument("--max", type=int, default=None,
                    help="Cap the number of enrichments this run (debug / rate-limit).")
    ap.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None)
    args = ap.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(level)

    all_ips = ipenrich.collect_torrent_health_ips()
    logger.info("collected %d unique peer IPs from torrent_health scans", len(all_ips))

    if args.force:
        todo = sorted(all_ips)
    else:
        todo = sorted(ip for ip in all_ips if not ipenrich.is_cached(ip))
    if args.max:
        todo = todo[: args.max]

    if not todo:
        logger.info("nothing to enrich (all cached)")
        sys.exit(0)

    logger.info("%d IPs to enrich", len(todo))

    t0 = time.time()
    ok = fail = 0
    for i, ip in enumerate(todo, 1):
        try:
            rec = ipenrich.enrich(ip, force=args.force)
            if rec.get("asn") or rec.get("ptr"):
                ok += 1
            else:
                # CIRCL returned nothing usable, but we still wrote a record so
                # subsequent lazy UI calls don't refetch for a week.
                ok += 1
            if i % 50 == 0:
                logger.info("progress %d/%d", i, len(todo))
        except Exception as e:
            fail += 1
            logger.warning("enrich failed for %s: %s", ip, e)

    dt = time.time() - t0
    rate = len(todo) / dt if dt > 0 else 0.0
    logger.info("done: enriched=%d failed=%d in %.1fs (%.1f/s)", ok, fail, dt, rate)
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
