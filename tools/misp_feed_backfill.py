#!/usr/bin/env python3
"""
Backfill the local MISP feed (and push, if enabled) from the existing Valkey
state. The runtime hooks only fire on new/edited entries, so the feed starts
empty ; run this once after enabling misp_feed to publish the whole history.

    poetry run python tools/misp_feed_backfill.py            # groups + victims
    poetry run python tools/misp_feed_backfill.py --groups-only
    poetry run python tools/misp_feed_backfill.py --victims-only
"""
import argparse
import json

import valkey

from ransomlook.default import DB_GROUPS, DB_POSTS, get_socket_path
from ransomlook.misp_feed import enabled, push_enabled, refresh_group, refresh_victim


def getdb(db: int) -> valkey.Valkey:
    return valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)


def backfill_groups() -> int:
    red = getdb(DB_GROUPS)
    count = 0
    for key in red.keys():  # type: ignore[union-attr]
        name = key.decode()
        if refresh_group(name):
            count += 1
    print("groups: %d infrastructure events" % count)
    return count


def backfill_victims() -> int:
    red = getdb(DB_POSTS)
    count = 0
    for key in red.keys():  # type: ignore[union-attr]
        name = key.decode()
        posts = json.loads(red.get(name))  # type: ignore[arg-type]
        for post in posts:
            title = post.get("post_title")
            if title and refresh_victim(name, title):
                count += 1
        print("  %s: done (%d total)" % (name, count))
    print("victims: %d events" % count)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill the local MISP feed from Valkey")
    parser.add_argument("--groups-only", action="store_true", help="Only rebuild group infrastructure events")
    parser.add_argument("--victims-only", action="store_true", help="Only rebuild victim events")
    args = parser.parse_args()

    if not (enabled() or push_enabled()):
        print("misp_feed disabled and misp push disabled — nothing to do (enable one in config).")
        return

    if not args.victims_only:
        backfill_groups()
    if not args.groups_only:
        backfill_victims()


if __name__ == "__main__":
    main()
