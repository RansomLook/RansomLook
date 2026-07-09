#!/usr/bin/env python3
import json
import uuid
from datetime import datetime

import valkey

from ransomlook.bluesky import blueskynotify
from ransomlook.default import DB_ALERTS, DB_POSTS, DB_TASKS
from ransomlook.default.config import get_config, get_socket_path
from ransomlook.default.logging import get_logger
from ransomlook.email import alertingnotify
from ransomlook.mastodon import tootnotify
from ransomlook.misp_feed import refresh_victim
from ransomlook.rocket import rocketnotify
from ransomlook.sharedutils import dbglog, errlog, stdlog

logger = get_logger("posts")


def posttemplate(
    victim: str, description: str, link: str | None, timestamp: str, magnet: str | None, screen: str | None
) -> dict[str, str | None]:
    """
    assuming we have a new post - form the template we will use for the new entry in posts.json
    """
    schema = {
        "post_title": victim,
        "discovered": timestamp,
        "description": description,
        "link": link,
        "magnet": magnet,
        "screen": screen,
        "misp_uuid": None,
    }
    stdlog("new post: " + victim)
    dbglog(schema)
    return schema


def _get_red(db: int) -> valkey.Valkey:
    """Create a Valkey connection for the given db."""
    return valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)


def appender(entry: dict[str, str | None] | str, group_name: str) -> int:
    """
    append a new post to posts.json
    """
    rocketconfig = get_config("generic", "rocketchat")
    mastodonconfig = get_config("generic", "mastodon")
    blueskyconfig = get_config("generic", "bluesky")
    emailconfig = get_config("generic", "email")
    siteurl = get_config("generic", "siteurl")
    if type(entry) is str:
        post_title = entry
        description = ""
        link = None
        magnet = None
        screen = None
    else:
        post_title = entry["title"]  # type: ignore[index,assignment]
        description = entry["description"]  # type: ignore[index,assignment]
        if "link" in entry:
            link = entry["link"]  # type: ignore[index]
        else:
            link = None
        if "magnet" in entry:
            magnet = entry["magnet"]  # type: ignore[index]
        else:
            magnet = None
        if "screen" in entry:
            screen = entry["screen"]  # type: ignore[index]
        else:
            screen = None
    if len(post_title) == 0:
        errlog("post_title is empty")
        return 2
    # limit length of post_title to 90 chars
    if len(post_title) > 90:
        post_title = post_title[:90]
    red = _get_red(DB_POSTS)
    posts = []

    if red.exists(group_name):
        posts = json.loads(red.get(group_name))  # type: ignore[arg-type]
        for post in posts:
            if post["post_title"] == post_title:
                stdlog("post already existing")
                logger.debug("existing post: %s", post)
                return 1
    newpost = posttemplate(
        post_title, description, link, str(entry["date"]) if "date" in entry else str(datetime.today()), magnet, screen  # type: ignore[index]
    )
    stdlog("adding new post: " + "group: " + group_name + " title: " + post_title)
    posts.append(newpost)
    red.set(group_name, json.dumps(posts))
    # preparing to screen
    if link is not None and link != "" and not screen:
        screenred = _get_red(DB_TASKS)
        if b"toscan" not in screenred.keys():  # type: ignore[operator]
            toscan = []
        else:
            toscan = json.loads(screenred.get("toscan"))  # type: ignore[arg-type]
        toscan.append({"group": group_name, "title": entry["title"], "slug": entry["slug"], "link": entry["link"]})  # type: ignore[index]
        screenred.set("toscan", json.dumps(toscan))
    # preparing to torrent
    if magnet is not None and magnet != "":
        torrentred = _get_red(DB_TASKS)
        if b"totorrent" not in torrentred.keys():  # type: ignore[operator]
            totorrent = []
        else:
            totorrent = json.loads(torrentred.get("totorrent"))  # type: ignore[arg-type]
        totorrent.append({"group": group_name, "title": entry["title"], "magnet": entry["magnet"]})  # type: ignore[index]
        torrentred.set("totorrent", json.dumps(totorrent))
    # Notification zone
    red_task = _get_red(DB_TASKS)
    keywords = red_task.get("keywords")
    matching = []
    if keywords is not None:
        listkeywords = keywords.decode().splitlines()  # type: ignore[union-attr]
        for keywordfull in listkeywords:
            keyword = keywordfull.split("|")[0]
            if keyword.lower() in post_title.lower() or keyword.lower() in description.lower():
                matching.append(keyword)
        if matching:
            alertingnotify(emailconfig, group_name, post_title, description, matching)
            alertdb = _get_red(DB_ALERTS)
            uuidkey = str(uuid.uuid4())
            value = {
                "type": "group",
                "group_name": group_name,
                "post_title": post_title,
                "description": description,
                "matching": matching,
            }
            alertdb.set(uuidkey, json.dumps(value))
            alertdb.expire(uuidkey, 60 * 60 * 24)

    if rocketconfig["enable"] == True:
        rocketnotify(rocketconfig, group_name, post_title, description)
    if mastodonconfig["enable"] == True:
        tootnotify(mastodonconfig, group_name, post_title, siteurl)
    if blueskyconfig["enable"] == True:
        blueskynotify(blueskyconfig, group_name, post_title, siteurl)
    # MISP local feed + push (upsert on the shared deterministic uuid)
    refresh_victim(group_name, post_title)
    return 0
