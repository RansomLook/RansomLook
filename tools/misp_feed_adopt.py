#!/usr/bin/env python3
"""
One-shot adoption of already-pushed MISP events.

Old pushed events (from the previous mispevent() code) have random UUIDs. This
maps each of them back to its victim in Valkey and stores the *existing* event
UUID as post["misp_uuid"], so future updates (feed + push) target the same
already-published event instead of creating a duplicate.

Matching relies on the old event layout:
    event.info  == "<Group> new post : <title>"
    object "ransomware-group-post" attribute "title" == <title>

Dry-run by default ; pass --commit to actually write the UUIDs into Valkey.

    poetry run python tools/misp_feed_adopt.py           # preview matches
    poetry run python tools/misp_feed_adopt.py --commit  # write misp_uuid
"""
import argparse
import json

import valkey
from pymisp import MISPEvent, PyMISP

from ransomlook.default import DB_POSTS, get_socket_path
from ransomlook.default.config import get_config


def getdb(db: int) -> valkey.Valkey:
    return valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)


def event_identity(event: MISPEvent) -> tuple[str, str] | None:
    """
    return (group_key, title) parsed from an old pushed event, or None
    """
    info = event.info or ""
    if " new post : " not in info:
        return None
    group = info.split(" new post : ", 1)[0].strip().lower()

    title = ""
    for obj in getattr(event, "objects", []):
        if obj.name != "ransomware-group-post":
            continue
        for attr in obj.attributes:
            if attr.object_relation == "title":
                title = str(attr.value)
                break
    if not title:
        # fall back to the info suffix
        title = info.split(" new post : ", 1)[1].strip()
    if not group or not title:
        return None
    return group, title


def find_post(posts: list[dict], title: str) -> dict | None:
    """
    match a victim by exact title, or by the 90-char truncation used in Valkey
    """
    for post in posts:
        stored = post.get("post_title") or ""
        if stored == title:
            return post
    for post in posts:
        stored = post.get("post_title") or ""
        if len(stored) == 90 and title.startswith(stored):
            return post
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Adopt existing pushed MISP event UUIDs into Valkey")
    parser.add_argument("--commit", action="store_true", help="Write misp_uuid into Valkey (default: dry-run)")
    args = parser.parse_args()

    config = get_config("generic", "misp")
    misp = PyMISP(url=config["url"], key=config["apikey"], ssl=config["tls_verify"])

    orgc_uuid = get_config("generic", "misp_feed").get("orgc_uuid") if get_config("generic", "misp_feed") else None
    if orgc_uuid:
        events = misp.search(controller="events", org=orgc_uuid, pythonify=True)
    else:
        events = misp.search(controller="events", pythonify=True)

    red = getdb(DB_POSTS)
    matched = 0
    skipped = 0
    changed_groups: dict[str, list] = {}

    for event in events:
        identity = event_identity(event)
        if identity is None:
            skipped += 1
            continue
        group, title = identity
        raw = red.get(group)
        if not raw:
            skipped += 1
            continue
        posts = changed_groups.get(group) or json.loads(raw)  # type: ignore[arg-type]
        post = find_post(posts, title)
        if post is None:
            skipped += 1
            continue
        if post.get("misp_uuid") == event.uuid:
            continue
        print("%s / %s -> %s" % (group, title, event.uuid))
        post["misp_uuid"] = event.uuid
        changed_groups[group] = posts
        matched += 1

    if args.commit:
        for group, posts in changed_groups.items():
            red.set(group, json.dumps(posts))
        print("committed: %d victims adopted across %d groups" % (matched, len(changed_groups)))
    else:
        print("dry-run: %d victims would be adopted (%d events skipped). Re-run with --commit." % (matched, skipped))


if __name__ == "__main__":
    main()
