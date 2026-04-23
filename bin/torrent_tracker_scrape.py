#!/usr/bin/env python3
"""CLI wrapper — run BEP-48 scrape over all known torrents.

Typical cron::

    0 */3 * * * cd /opt/ransomlook && poetry run torrent-tracker-scrape

Flags::

    --limit N       max batches (for testing)
    --clearnet-too  also scrape clearnet trackers (off by default — Tor only)
    --verbose       DEBUG logging
"""
from __future__ import annotations

import argparse
import logging
import sys

from ransomlook import torrent_tracker_scrape as tts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N tracker batches (default: exhaustive).")
    ap.add_argument("--clearnet-too", action="store_true",
                    help="Also scrape clearnet trackers. Off by default — onion only.")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="DEBUG logging.")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        force=True,
    )
    if args.verbose:
        logging.getLogger("ransomlook.torrent_tracker_scrape").setLevel(logging.DEBUG)

    res = tts.run_once(limit=args.limit, clearnet_too=args.clearnet_too)
    print(f"scraped={res['scraped']} trackers={res['trackers']} "
          f"batches={res['batches']} errors={res['errors']} elapsed={res['elapsed']}s")
    return 0 if res["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
