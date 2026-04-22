#!/usr/bin/env python3
"""Back-fill ``magnet`` fields on Clop posts from a scraped HTML snippet.

The input file (passed as the only positional argument) contains one
victim per line of the form::

    <strong> <p style="color: red;"> VICTIM.TLD - PUBLISHED VIA TORRENT,
    MAGNET LINK --&gt; <a href="magnet:?xt=urn:btih:..."> CLICK HERE</a>
    [optional second magnet] </p> </strong>

We extract the first ``magnet:?...`` URI per victim and, for every post
already present in ``DB_POSTS`` under the Clop key whose ``post_title``
matches a victim name (case-insensitive), fill the ``magnet`` field only
when it is currently empty.

The script is **read-only by default** (dry-run). Pass ``--apply`` to
actually write the updated posts back to Valkey.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import valkey

from ransomlook.default import DB_POSTS, get_socket_path


VICTIM_LINE = re.compile(
    r"""
    (?P<victim>[A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,})   # domain-like name
    \s*-\s*PUBLISHED\s+VIA\s+TORRENT.*?                    # keyword
    href="(?P<magnet>magnet:\?xt=urn:btih:[^"]+)"          # first magnet URI
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


def parse_clop(path: Path) -> dict[str, str]:
    """Return ``{victim_lower: magnet_uri}`` (first magnet only per victim)."""
    out: dict[str, str] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in VICTIM_LINE.finditer(text):
        victim = m.group("victim").strip().lower()
        magnet = m.group("magnet").strip()
        out.setdefault(victim, magnet)  # keep only the first
    return out


def find_clop_key(red: valkey.Valkey) -> str | None:
    """Return the DB_POSTS key for Clop (case-insensitive), or None."""
    for key in red.keys():  # type: ignore[union-attr]
        name = key.decode()
        if name.lower() == "clop":
            return name
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path,
                    help="Path to the scraped HTML snippet (e.g. clop.txt).")
    ap.add_argument("--apply", action="store_true",
                    help="Persist updates to Valkey. Default is dry-run.")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    path = args.input
    if not path.is_file():
        print(f"error: input file not found: {path}", file=sys.stderr)
        return 2

    mapping = parse_clop(path)
    if not mapping:
        print("error: no victims parsed from", path, file=sys.stderr)
        return 2
    print(f"parsed {len(mapping)} victims from {path}")

    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
    key = find_clop_key(red)
    if not key:
        print("error: no Clop key found in DB_POSTS", file=sys.stderr)
        return 2
    print(f"Clop key in DB_POSTS: {key!r}")

    raw = red.get(key)
    if not raw:
        print("error: empty value for", key, file=sys.stderr)
        return 2
    posts = json.loads(raw)
    if not isinstance(posts, list):
        print("error: posts is not a list", file=sys.stderr)
        return 2
    print(f"{len(posts)} posts in {key!r}")

    matched = filled = skipped_existing = unmatched_victims = 0
    victim_used = set()
    for post in posts:
        if not isinstance(post, dict):
            continue
        title = str(post.get("post_title") or "").strip().lower()
        if not title:
            continue
        # Try direct match first, then strip common prefixes
        candidates_keys = [title, title.removeprefix("www.")]
        magnet = None
        for k in candidates_keys:
            if k in mapping:
                magnet = mapping[k]
                victim_used.add(k)
                break
        if magnet is None:
            continue
        matched += 1
        existing = (post.get("magnet") or "").strip()
        if existing:
            skipped_existing += 1
            if args.verbose:
                print(f"  = {post.get('post_title')!r}  (already has magnet, skip)")
            continue
        post["magnet"] = magnet
        filled += 1
        if args.verbose:
            print(f"  + {post.get('post_title')!r}  <- {magnet[:60]}…")

    unmatched_victims = sum(1 for v in mapping if v not in victim_used)

    print()
    print(f"matched   : {matched} post(s)")
    print(f"filled    : {filled} post(s)")
    print(f"already ok: {skipped_existing} post(s) had a magnet")
    print(f"no post   : {unmatched_victims} victim(s) from clop.txt had no matching post")

    if args.apply:
        red.set(key, json.dumps(posts))
        print("\napplied: Valkey updated ✓")
    else:
        print("\ndry-run: nothing written. Add --apply to persist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
