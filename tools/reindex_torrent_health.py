#!/usr/bin/env python3
"""Backfill IP/ASN pivot indexes for existing torrent-health scans.

The :func:`store_scan <ransomlook.torrent_health.store_scan>` function only
started populating ``ip_to_ih``, ``ip_seeds``, ``top:ip`` and ``top:ip_seed``
as of the pivot-indexing release. Scans stored before that have no indexes,
so the /admin/torrent-health/ips page would show incomplete data. This script
reads every scan entry in DB_TORRENT_HEALTH and rebuilds the indexes from
scratch.

Safe to run at any time: the target zsets are cleared at the start and
rewritten from ground truth. Takes a few seconds per thousand scans.

Usage::

    poetry run tools/reindex_torrent_health.py           # reindex everything
    poetry run tools/reindex_torrent_health.py --dry-run # count only, no writes
"""

from __future__ import annotations

import argparse
import json
import sys

import valkey

from ransomlook.default import DB_TORRENT_HEALTH, get_socket_path
from ransomlook.torrent_health import _ignored_ips


IP_INDEX_PREFIXES = [
    "torrent_health:ip_to_ih:",
    "torrent_health:ip_seeds:",
    "torrent_health:ip_to_groups:",
    "torrent_health:asn_to_ih:",
    "torrent_health:asn_to_ip:",
    "torrent_health:asn_seed_ih:",
    "torrent_health:asn_seed_ips:",
]
IP_LEADERBOARDS = [
    "torrent_health:top:ip",
    "torrent_health:top:ip_seed",
    "torrent_health:top:ip_cross_group",
    "torrent_health:top:asn",
    "torrent_health:top:asn_seed",
]


def _wipe_old_indexes(r: valkey.Valkey) -> int:
    removed = 0
    for prefix in IP_INDEX_PREFIXES:
        for key in r.scan_iter(match=f"{prefix}*"):
            r.delete(key)
            removed += 1
    for key in IP_LEADERBOARDS:
        r.delete(key)
    return removed


def _is_seeder_flags(flags: str, progress: float) -> bool:
    return "seed" in (flags or "") or float(progress or 0) >= 99.9


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Count scans and IPs but write nothing.")
    ap.add_argument("--skip-asn", action="store_true",
                    help="Rebuild only the IP indexes. Skip the ASN indexes "
                         "(they are populated lazily via ipenrich.enrich()).")
    args = ap.parse_args()

    r = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TORRENT_HEALTH)

    scans = list(r.scan_iter(match="torrent_health:scan:*"))
    print(f"found {len(scans)} scan entries in DB_TORRENT_HEALTH")

    if args.dry_run:
        ip_count = 0
        for key in scans:
            raw: bytes | None = r.get(key)  # type: ignore[assignment]
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            ip_count += len(payload.get("peers") or [])
        print(f"dry-run: would index {ip_count} peer observations (no writes)")
        return 0

    print("wiping existing pivot indexes…")
    wiped = _wipe_old_indexes(r)
    print(f"  removed {wiped} key(s)")

    indexed_ips = 0
    indexed_scans = 0
    skipped_ignored = 0
    ignored = _ignored_ips()
    if ignored:
        print(f"honoring {len(ignored)} ignored IP(s) from config")
    touched_ips: set[str] = set()
    # Cache groups per infohash so we don't HGETALL the meta on every scan.
    ih_groups_cache: dict[str, list[str]] = {}

    def _groups_for_ih(ih: str) -> list[str]:
        if ih in ih_groups_cache:
            return ih_groups_cache[ih]
        raw_meta: bytes | None = r.hget(f"torrent_health:meta:{ih}", "groups")  # type: ignore[assignment]
        grps: list[str] = []
        if raw_meta:
            try:
                grps = json.loads(raw_meta) or []
            except Exception:
                grps = []
        ih_groups_cache[ih] = grps
        return grps

    for key in scans:
        key_str = key.decode()
        # Key format: torrent_health:scan:<infohash>:<ts>
        parts = key_str.split(":", 3)
        if len(parts) < 4:
            continue
        ih = parts[2]
        raw2: bytes | None = r.get(key)  # type: ignore[assignment]
        if not raw2:
            continue
        try:
            payload = json.loads(raw2)
        except Exception:
            continue
        peers = payload.get("peers") or []
        indexed_scans += 1
        groups = _groups_for_ih(ih)
        for peer in peers:
            ip = (peer.get("ip") or "").strip()
            if not ip or ip == "?":
                continue
            if ip in ignored:
                skipped_ignored += 1
                continue
            flags = peer.get("flags") or ""
            progress = peer.get("progress") or 0
            r.sadd(f"torrent_health:ip_to_ih:{ip}", ih)
            r.zincrby("torrent_health:top:ip", 1, ip)
            if _is_seeder_flags(flags, progress):
                r.sadd(f"torrent_health:ip_seeds:{ip}", ih)
                r.zincrby("torrent_health:top:ip_seed", 1, ip)
            # Cross-group: track every ransomware group this IP has touched.
            for grp in groups:
                if grp:
                    r.sadd(f"torrent_health:ip_to_groups:{ip}", grp)
            touched_ips.add(ip)
            indexed_ips += 1

    # Finalize the cross-group leaderboard from the per-IP group sets.
    cross_group_count = 0
    for ip in touched_ips:
        group_count: int = r.scard(f"torrent_health:ip_to_groups:{ip}") or 0  # type: ignore[assignment]
        if group_count >= 2:
            r.zadd("torrent_health:top:ip_cross_group", {ip: group_count})
            cross_group_count += 1

    ip_lb_count: int = r.zcard("torrent_health:top:ip") or 0  # type: ignore[assignment]
    seed_lb_count: int = r.zcard("torrent_health:top:ip_seed") or 0  # type: ignore[assignment]
    print(f"indexed {indexed_ips} peer observations across {indexed_scans} scans")
    if skipped_ignored:
        print(f"skipped {skipped_ignored} peer observation(s) matching ignored_ips")
    print(f"IP leaderboard: {ip_lb_count} entries")
    print(f"cross-group leaderboard: {cross_group_count} IPs touching 2+ groups")
    print(f"seeder leaderboard: {seed_lb_count} entries")

    if args.skip_asn:
        print("--skip-asn: ASN indexes left untouched.")
        return 0

    # Now rebuild the ASN indexes by iterating over the enrichment cache.
    # Any IP we've indexed above that also has a cached enrichment gets its
    # ASN-side indexes repopulated. IPs without cached enrichment will be
    # filled lazily when enrich() runs (or via `poetry run enrich-ips`).
    print("rebuilding ASN indexes from cached enrichments…")
    from ransomlook.ipenrich import _index_ip_asn
    asn_done = 0
    for key in r.scan_iter(match="ipenrich:*"):
        raw3: bytes | None = r.get(key)  # type: ignore[assignment]
        if not raw3:
            continue
        try:
            rec = json.loads(raw3)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        ip = rec.get("ip") or ""
        asn = rec.get("asn")
        if not ip or not asn:
            continue
        try:
            _index_ip_asn(ip, asn)
            asn_done += 1
        except Exception as e:
            print(f"  warn: {ip} → {e}", file=sys.stderr)
    asn_count: int = r.zcard("torrent_health:top:asn") or 0  # type: ignore[assignment]
    print(f"ASN indexes updated for {asn_done} IP(s).")
    print(f"ASN leaderboard: {asn_count} entries")

    return 0


if __name__ == "__main__":
    sys.exit(main())
