#!/usr/bin/env python3
"""Register a torrent under a ransomware group without requiring a post.

Some groups publish leaks outside the mainstream DLS flow (Telegram drops,
forum posts, private mirrors) and RansomLook never ingests those via the
``/ransomlook/parsers/`` pipeline. This CLI lets you attach a magnet or
.torrent file to a group so the torrent-health worker picks it up and so
the pivot dashboards link it to the right family.

Examples::

    # Single magnet
    poetry run tools/add_group_torrent.py --group clop --magnet "magnet:?xt=urn:btih:..."

    # A .torrent file (magnet is derived via libtorrent)
    poetry run tools/add_group_torrent.py --group akira --torrent /path/to/leak.torrent

    # Several at once (repeatable flags, all attached to the same group)
    poetry run tools/add_group_torrent.py --group ransomhub \\
        --magnet "magnet:?xt=urn:btih:a..." \\
        --magnet "magnet:?xt=urn:btih:b..." \\
        --torrent /tmp/leak1.torrent

    # Bulk from a file (one magnet OR .torrent path per line)
    poetry run tools/add_group_torrent.py --group akira --from-file magnets.txt

Remove a torrent::

    poetry run tools/add_group_torrent.py --remove <infohash>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ransomlook import torrent_health as th


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", help="Ransomware group name to attach the torrent(s) to.")
    ap.add_argument("--magnet", action="append", default=[],
                    help="Magnet URI. Repeatable.")
    ap.add_argument("--torrent", action="append", default=[],
                    help="Path to a .torrent file. Repeatable.")
    ap.add_argument("--from-file",
                    help="Path to a text file containing one magnet or .torrent path per line.")
    ap.add_argument("--remove",
                    help="Infohash to remove (meta + scan history). Mutually exclusive with adding.")
    args = ap.parse_args()

    # ── Remove path ───────────────────────────────────────────────────────
    if args.remove:
        ih = args.remove.strip().lower()
        ok = th.delete_manual_torrent(ih)
        if ok:
            print(f"removed torrent {ih}")
            return 0
        print(f"error: nothing to remove for {ih}", file=sys.stderr)
        return 2

    # ── Add path ──────────────────────────────────────────────────────────
    if not args.group:
        ap.error("--group is required when adding torrents")

    sources: list[str] = list(args.magnet) + list(args.torrent)
    if args.from_file:
        p = Path(args.from_file)
        if not p.is_file():
            print(f"error: --from-file {p} not found", file=sys.stderr)
            return 2
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)

    if not sources:
        ap.error("provide at least one --magnet, --torrent or --from-file")

    added = 0
    merged = 0
    failed = 0
    for src in sources:
        try:
            info = th.add_manual_torrent(args.group, src)
        except Exception as e:
            print(f"✗ {src[:80]}: {e}", file=sys.stderr)
            failed += 1
            continue
        if info["already_tracked"]:
            merged += 1
            tag = "merged"
        else:
            added += 1
            tag = "added"
        print(f"✓ {tag} {info['infohash']}  ({info['name'] or '(no name)'})  groups={info['groups']}")

    print()
    print(f"summary: {added} new · {merged} merged · {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
