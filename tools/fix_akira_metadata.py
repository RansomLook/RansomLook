#!/usr/bin/env python3
"""Clean up Akira-ingested torrent meta corrupted by the early extraction bug.

Akira's DLS inserts ``\n`` characters every ~50 characters in every text
field of the JSON listing response (name, description, magnet URL). An
earlier version of the browser scraper stopped regex extraction at the
first ``\n`` inside the magnet, which produced:

* truncated magnets (ending mid-``tr=udp://tracker.o``),
* torrent names with embedded newlines (``mk Technolog\\ny Group\\n``),
* similarly haché ``comment`` strings.

This script walks every ``torrent_health:meta:*`` hash and:

* strips ``\n`` / ``\r`` / trailing whitespace from ``name`` and ``comment``
* drops from ``meta.magnets`` any magnet containing whitespace OR a ``tr=``
  that looks cut (not a well-formed URL) — keeps only magnets that are
  complete on their own
* if the magnets list ends up empty, leaves the meta alone and reports

Run in ``--dry-run`` first. The fixed scraper (post-regex patch) can then
re-import clean magnets via ``tools/add_group_torrent.py`` — the
``add_manual_torrent`` merge will add them alongside what remains.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from typing import Any
from urllib.parse import urlparse

from ransomlook.torrent_health import _redis

logger = logging.getLogger(__name__)

# A magnet is "clean" when it contains no whitespace and every ``tr=`` / ``ws=``
# parameter parses as a proper absolute URL (scheme + host + port|path).
_MAGNET_RE = re.compile(r"^magnet:\?xt=urn:btih:[0-9a-fA-F]{40,64}", re.IGNORECASE)


def _tracker_complete(tr_value: str) -> bool:
    """Return True if ``tr=`` value looks like a usable tracker URL."""
    try:
        p = urlparse(tr_value)
    except Exception:
        return False
    if p.scheme not in {"http", "https", "udp", "ws", "wss"}:
        return False
    if not p.hostname:
        return False
    # Require either an explicit port or a non-empty path (``.../announce``).
    if p.port is None and not p.path.strip("/"):
        return False
    return True


def _clean_magnet(magnet: str) -> str | None:
    """Return the magnet if it's well-formed, else None."""
    if not magnet or any(c.isspace() for c in magnet):
        return None
    if not _MAGNET_RE.match(magnet):
        return None
    # Parse out every tr= and ws= param manually — urlparse loses them
    # because magnets aren't standard URLs.
    try:
        q = magnet.split("?", 1)[1]
    except IndexError:
        return None
    params = [p.split("=", 1) for p in q.split("&") if "=" in p]
    for k, v in params:
        k = k.lower()
        if k in {"tr", "ws", "xs", "as"}:
            # Percent-decode the tracker/webseed URL before shape-checking.
            from urllib.parse import unquote
            if not _tracker_complete(unquote(v)):
                return None
    return magnet


def _clean_text(val: str) -> str:
    """Strip embedded newlines + trim."""
    return re.sub(r"[\r\n]+", "", val).strip()


def fix_meta(dry_run: bool = True, only_akira: bool = False) -> dict[str, int]:
    r = _redis()
    stats = {"scanned": 0, "name_fixed": 0, "comment_fixed": 0,
             "magnets_total": 0, "magnets_dropped": 0,
             "meta_updated": 0, "meta_empty_magnets": 0}

    for key in r.scan_iter(match="torrent_health:meta:*", count=500):
        stats["scanned"] += 1
        raw: dict[bytes, bytes] = r.hgetall(key)  # type: ignore[assignment]
        ih = key.decode().split(":", 2)[2]

        # Optional scope: only rows associated with the akira group.
        if only_akira:
            try:
                groups = json.loads(raw.get(b"groups", b"[]").decode() or "[]")
            except Exception:
                groups = []
            if "akira" not in [g.lower() for g in groups]:
                continue

        updates: dict[str, str] = {}

        # --- name / comment ----------------------------------------------
        for field in ("name", "comment"):
            val = raw.get(field.encode(), b"").decode()
            if not val:
                continue
            cleaned = _clean_text(val)
            if cleaned != val:
                updates[field] = cleaned
                stats[f"{field}_fixed"] += 1

        # --- magnets list ------------------------------------------------
        try:
            magnets = json.loads(raw.get(b"magnets", b"[]").decode() or "[]")
            if not isinstance(magnets, list):
                magnets = []
        except Exception:
            magnets = []

        stats["magnets_total"] += len(magnets)
        kept: list[str] = []
        dropped: list[str] = []
        for m in magnets:
            if not isinstance(m, str):
                continue
            cleaned_magnet = _clean_magnet(m)
            if cleaned_magnet is None:
                dropped.append(m)
                stats["magnets_dropped"] += 1
            else:
                kept.append(cleaned_magnet)

        if dropped:
            if kept:
                updates["magnets"] = json.dumps(sorted(set(kept)))
            else:
                # All magnets were bad — don't blank the field (we'd lose
                # any way to reimport), but flag it for the operator.
                stats["meta_empty_magnets"] += 1
                logger.warning("%s: all %d magnets dropped, field left untouched",
                               ih, len(dropped))

        if updates:
            stats["meta_updated"] += 1
            logger.info("%s: fix %s (kept=%d dropped=%d)", ih,
                        ", ".join(updates.keys()), len(kept), len(dropped))
            if not dry_run:
                r.hset(key, mapping=updates)

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="Actually write the fixes (default: dry-run).")
    ap.add_argument("--only-akira", action="store_true",
                    help="Limit scope to rows tagged with the 'akira' group.")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )

    stats = fix_meta(dry_run=not args.apply, only_akira=args.only_akira)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"--- {mode} ---")
    for k, v in stats.items():
        print(f"{k:>22}: {v}")
    if not args.apply:
        print("\nRe-run with --apply to persist the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
