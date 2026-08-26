#!/usr/bin/env python3
"""
Backfill the local MISP feed (and push, if enabled) from the existing Valkey
state. The runtime hooks only fire on new/edited entries, so the feed starts
empty ; run this once after enabling misp_feed to publish the whole history.

    poetry run python tools/misp_feed_backfill.py            # groups + markets + actors + victims
    poetry run python tools/misp_feed_backfill.py --groups-only
    poetry run python tools/misp_feed_backfill.py --markets-only
    poetry run python tools/misp_feed_backfill.py --actors-only
    poetry run python tools/misp_feed_backfill.py --victims-only
"""
import argparse

import valkey

from ransomlook.default import DB_ACTORS, DB_GROUPS, DB_MARKETS, DB_POSTS, get_socket_path
from ransomlook.misp_feed import enabled, push_enabled, refresh_actor, refresh_group, refresh_group_victims, refresh_market


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


def backfill_markets() -> int:
    red = getdb(DB_MARKETS)
    count = 0
    for key in red.keys():  # type: ignore[union-attr]
        name = key.decode()
        if refresh_market(name):
            count += 1
    print("markets: %d infrastructure events" % count)
    return count


def backfill_actors() -> int:
    red = getdb(DB_ACTORS)
    count = 0
    for key in red.keys():  # type: ignore[union-attr]
        name = key.decode()
        if refresh_actor(name):
            count += 1
    print("actors: %d events" % count)
    return count


def backfill_victims() -> int:
    """
    Rebuild every victim event. This also drops the events of entities that are
    private today, so it doubles as the cleanup pass for feeds built before
    refresh_group_victims() existed and kept serving a private group's victims.
    """
    red = getdb(DB_POSTS)
    count = 0
    for key in red.keys():  # type: ignore[union-attr]
        name = key.decode()
        handled = refresh_group_victims(name)
        count += handled
        print("  %s: %d posts (%d total)" % (name, handled, count))
    print("victims: %d posts processed" % count)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill the local MISP feed from Valkey")
    parser.add_argument("--groups-only", action="store_true", help="Only rebuild group infrastructure events")
    parser.add_argument("--markets-only", action="store_true", help="Only rebuild market / forum infrastructure events")
    parser.add_argument("--actors-only", action="store_true", help="Only rebuild threat actor events")
    parser.add_argument("--victims-only", action="store_true", help="Only rebuild victim events")
    args = parser.parse_args()

    if not (enabled() or push_enabled()):
        print("misp_feed disabled and misp push disabled — nothing to do (enable one in config).")
        return

    only = [args.groups_only, args.markets_only, args.actors_only, args.victims_only]
    run_all = not any(only)
    if run_all or args.groups_only:
        backfill_groups()
    if run_all or args.markets_only:
        backfill_markets()
    if run_all or args.actors_only:
        backfill_actors()
    if run_all or args.victims_only:
        backfill_victims()


if __name__ == "__main__":
    main()
