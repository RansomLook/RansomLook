#!/usr/bin/env python3
"""CLI — HEAD-check every webseed across all tracked torrents via Tor.

Typical cron (every 6h for instance)::

    0 */6 * * * cd /opt/ransomlook && poetry run torrent-webseed-check

Flags::

    --limit N       cap unique URLs probed (for testing)
    --workers N     concurrent threads (default 16)
    --onion-only    skip clearnet webseeds
    -v / --verbose  DEBUG logging
"""
from __future__ import annotations

import argparse
import logging
import sys

from ransomlook import torrent_webseed_check as twc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap on unique URLs to probe (default: all).")
    ap.add_argument("--workers", type=int, default=16,
                    help="Concurrent HEAD requests (default: 16).")
    ap.add_argument("--onion-only", action="store_true",
                    help="Skip clearnet webseeds.")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="DEBUG logging.")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        force=True,
    )
    # Silence urllib3 DEBUG chatter when we only want ours.
    if not args.verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    res = twc.run_once(limit=args.limit, workers=args.workers,
                       onion_only=args.onion_only)
    print(f"checked={res['checked']} up={res['up']} down={res['down']} "
          f"torrents={res['torrents']} elapsed={res['elapsed']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
