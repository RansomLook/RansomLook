#!/usr/bin/env python3

import glob
import json
import re
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta
from os.path import basename, dirname, isfile, join
from typing import Any
from urllib.parse import urlparse, urlsplit

import tldextract
import valkey

from ransomlook.default import DB_ACTORS, DB_CRYPTO, DB_GROUPS, DB_LEAKS, DB_MARKETS, DB_NOTES, DB_POSTS, DB_RF
from ransomlook.default.config import get_homedir, get_socket_path
from ransomlook.default.logging import get_logger

_logger = get_logger("shared")


def stdlog(msg: Any) -> None:
    """standard info logging"""
    _logger.info(msg)


def dbglog(msg: Any) -> None:
    """standard debug logging"""
    _logger.debug(msg)


def errlog(msg: Any) -> None:
    """standard error logging"""
    _logger.error(msg)


def honk(msg: Any) -> None:
    """critical error logging with termination"""
    _logger.critical(msg)
    sys.exit()


def get_private_entity_names() -> set[str]:
    """Return lowercase names of groups/markets flagged `private: true`.

    Posts and health series are keyed by group/market name in separate DBs
    without carrying the private flag. Callers use this set to filter
    aggregate endpoints that would otherwise leak private-group activity.
    """
    names: set[str] = set()
    for db_num in (DB_GROUPS, DB_MARKETS):
        red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db_num)
        for key in red.keys():  # type: ignore[union-attr]
            raw = red.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)  # type: ignore[arg-type]
            except Exception:
                continue
            if data.get("private") is True:
                names.add(key.decode().lower())
    return names


_GLOB_META_RE = re.compile(r"([\\*?\[\]])")


def escape_glob(value: str) -> str:
    """Escape Redis glob metacharacters so a value is safe in a SCAN MATCH pattern.

    Redis treats ``*``, ``?``, ``[``, ``]`` and ``\\`` as pattern syntax. A
    caller-supplied name carrying any of them would widen the scan to keys the
    caller must never reach — including those of entities flagged private.
    """
    return _GLOB_META_RE.sub(r"\\\1", value or "")


def norm_group_slug(value: str) -> str:
    """Slugify a group/market name the way DB_NOTES keys its indexes.

    Ransom notes are stored under `idx:group:<slug>:notes`, so any privacy
    check on notes has to compare slugs, not raw group names.
    """
    slug = (value or "").strip().lower().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9\-]+", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def get_private_group_slugs() -> set[str]:
    """Slugified names of the groups/markets flagged private."""
    return {norm_group_slug(name) for name in get_private_entity_names()}


def get_private_note_slugs() -> set[str]:
    """Every note slug that belongs to a private group or market.

    A note may be tagged with an alias rather than the canonical slug, so the
    private set is expanded with the aliases resolving to a private group —
    otherwise filtering on the canonical slug alone leaves the alias exposed.
    """
    private = get_private_group_slugs()
    if not private:
        return private
    try:
        red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)
        aliases = red.hgetall("alias:group") or {}
        for alias, canon in aliases.items():  # type: ignore[union-attr]
            if canon.decode() in private:
                private.add(alias.decode())
        for canon in list(private):
            for alias in red.smembers("group:" + canon + ":aliases") or []:  # type: ignore[union-attr]
                private.add(alias.decode())
    except Exception:
        pass
    return private


def note_is_private(note: Any, private_slugs: set[str]) -> bool:
    """True when a note is attached to at least one private group.

    Conservative on purpose: a note tagged with both a public and a private
    group still discloses the private association, so it stays hidden.
    """
    if not isinstance(note, dict):
        return False
    return any(str(group) in private_slugs for group in (note.get("groups") or []))


def is_private_post(post: Any) -> bool:
    """Return True when a post carries the `private: true` flag.

    Posts predate the flag, so an absent key means public.
    """
    return isinstance(post, dict) and post.get("private") is True


def public_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop the posts flagged private from a group's post list."""
    return [post for post in posts if not is_private_post(post)]


def parse_discovered(value: Any) -> datetime | None:
    """Parse a post `discovered` stamp, with or without microseconds.

    Returns None instead of raising: a single malformed stamp must not take
    down a whole aggregate.
    """
    if not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def iter_posts(
    include_private: bool = False, red: valkey.Valkey | None = None
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield `(group_name, post)` over the whole post database.

    Unless `include_private`, posts belonging to a group/market flagged
    private and posts flagged private themselves are skipped. This is the
    single filtering point every public aggregate should go through.
    """
    if red is None:
        red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
    private_names: set[str] = set() if include_private else get_private_entity_names()
    for key in red.keys():  # type: ignore[union-attr]
        group_name = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
        if not include_private and group_name.lower() in private_names:
            continue
        raw = red.get(key)
        if not raw:
            continue
        try:
            entries = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if not include_private and is_private_post(entry):
                continue
            yield group_name, entry


def gcount(posts: list[dict[str, Any]]) -> dict[str, int]:
    group_counts: dict[str, int] = {}
    for post in posts:
        if post["group_name"] in group_counts:
            group_counts[post["group_name"]] += 1
        else:
            group_counts[post["group_name"]] = 1
    return group_counts


def postcount(include_private: bool = False) -> int:
    """Total number of posts. Private groups and private posts are excluded
    unless the caller is entitled to see them."""
    return sum(1 for _ in iter_posts(include_private))


def groupcount(db: int) -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    groups = red.keys()
    return len(groups)  # type: ignore[arg-type]


def hostcount(db: int) -> int:
    hosts = []
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    groups = red.keys()
    for entry in groups:  # type: ignore[union-attr]
        group = json.loads(red.get(entry))  # type: ignore[arg-type]
        for host in group["locations"]:
            hosts.append(host["fqdn"])
    return len(set(hosts))


def hostcountdls(db: int) -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    groups = red.keys()
    hosts = []
    for entry in groups:  # type: ignore[union-attr]
        group = json.loads(red.get(entry))  # type: ignore[arg-type]
        for host in group["locations"]:
            if (
                ("chat" not in host or host["chat"] is False)
                and ("fs" not in host or host["fs"] is False)
                and ("admin" not in host or host["admin"] is False)
            ):
                hosts.append(host["fqdn"])
    return len(set(hosts))


def hostcountfs(db: int) -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    groups = red.keys()
    hosts = []
    for entry in groups:  # type: ignore[union-attr]
        group = json.loads(red.get(entry))  # type: ignore[arg-type]
        for host in group["locations"]:
            if "fs" in host and host["fs"] is True:
                hosts.append(host["fqdn"])
    return len(set(hosts))


def hostcountchat(db: int) -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    groups = red.keys()
    hosts = []
    for entry in groups:  # type: ignore[union-attr]
        group = json.loads(red.get(entry))  # type: ignore[arg-type]
        for host in group["locations"]:
            if "chat" in host and host["chat"] is True:
                hosts.append(host["fqdn"])
    return len(set(hosts))


def hostcountadmin(db: int) -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    groups = red.keys()
    hosts = []
    for entry in groups:  # type: ignore[union-attr]
        group = json.loads(red.get(entry))  # type: ignore[arg-type]
        for host in group["locations"]:
            if "admin" in host and host["admin"] is True:
                hosts.append(host["fqdn"])
    return len(set(hosts))


def postssince(days: int, include_private: bool = False) -> int:
    """returns the number of posts within the last x days"""
    cutoff = datetime.now() - timedelta(days=days)
    post_count = 0
    for _, post in iter_posts(include_private):
        discovered = parse_discovered(post.get("discovered"))
        if discovered is not None and discovered > cutoff:
            post_count += 1
    return post_count


def poststhisyear(include_private: bool = False) -> int:
    """returns the number of posts within the current year"""
    current_year = datetime.now().year
    post_count = 0
    for _, post in iter_posts(include_private):
        discovered = parse_discovered(post.get("discovered"))
        if discovered is not None and discovered.year == current_year:
            post_count += 1
    return post_count


def postslast24h(include_private: bool = False) -> int:
    """returns the number of posts within the last 24 hours"""
    cutoff = datetime.now() - timedelta(hours=24)
    post_count = 0
    for _, post in iter_posts(include_private):
        discovered = parse_discovered(post.get("discovered"))
        if discovered is not None and discovered > cutoff:
            post_count += 1
    return post_count


def actorcount() -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    return red.dbsize()  # type: ignore[return-value]


def cryptostats() -> dict[str, int]:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
    addr_count = 0
    tx_count = 0
    for key in red.scan_iter(match="crypto:addr:*"):
        addr_count += 1
        data = json.loads(red.get(key))  # type: ignore[arg-type]
        tx_count += len(data.get("transactions", []))
    return {"addresses": addr_count, "transactions": tx_count}


def notecount() -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)
    return red.dbsize()  # type: ignore[return-value]


def leakcount() -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)
    return red.dbsize()  # type: ignore[return-value]


def rfcount() -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_RF)
    return red.dbsize()  # type: ignore[return-value]


def parsercount() -> int:
    modules = glob.glob(join(dirname(str(get_homedir()) + "/" + "ransomlook/parsers/"), "*.py"))
    __all__ = [basename(f)[:-3] for f in modules if isfile(f) and not basename(f).startswith("_")]
    return len(__all__)


def onlinecount(db: int) -> int:
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)
    groups = red.keys()
    online_count = 0
    for entry in groups:  # type: ignore[union-attr]
        group = json.loads(red.get(entry))  # type: ignore[arg-type]
        for host in group["locations"]:
            if host["available"] is True:
                online_count += 1
    return online_count


def currentmonthstr() -> str:
    """
    return the current, full month name in lowercase
    """
    return datetime.now().strftime("%B").lower()


def mounthlypostcount(include_private: bool = False) -> int:
    """
    returns the number of posts within the current month
    """
    month_first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    post_count = 0
    for _, post in iter_posts(include_private):
        discovered = parse_discovered(post.get("discovered"))
        if discovered is not None and discovered > month_first_day:
            post_count += 1
    return post_count


def countcaptchahosts() -> int:
    """returns a count on the number of groups that have captchas"""
    red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    groups = red.keys()
    captcha_count = 0
    for entry in groups:  # type: ignore[union-attr]
        group = json.loads(red.get(entry))  # type: ignore[arg-type]
        if group["captcha"] is True:
            captcha_count += 1
    return captcha_count


"""
Ransomlook
"""


def siteschema(
    location: str, fs: bool, private: bool, chat: bool, admin: bool, browser: str | None, init_script: str | None
) -> dict[str, Any | None]:
    """
    returns a dict with the site schema
    """
    if not location.startswith("http"):
        dbglog("sharedutils: " + "assuming we have been given an fqdn and appending protocol")
        location = "http://" + location
    schema = {
        "fqdn": getapex(location),
        "title": None,
        "timeout": None,
        "delay": None,
        "version": getonionversion(location)[0],
        "slug": location,
        "available": False,
        "updated": str(datetime.today()),
        "fs": fs,
        "chat": chat,
        "admin": admin,
        "browser": browser,
        "init_script": init_script,
        "private": private,
        "lastscrape": "Never",
    }
    dbglog("sharedutils: " + "schema - " + str(schema))
    return schema


def getapex(slug: str) -> str:
    """
    returns the domain for a given webpage/url slug
    """
    stripurl = tldextract.extract(slug)
    dbglog("sharedutils: " + "stripurl - " + str(stripurl))
    if stripurl.subdomain:
        return stripurl.subdomain + "." + stripurl.domain + "." + stripurl.suffix
    else:
        return stripurl.domain + "." + stripurl.suffix


def getonionversion(slug: str) -> tuple[int, str]:
    """
    returns the version of an onion service (v2/v3)
    https://support.torproject.org/onionservices/v2-deprecation
    """
    version = None
    stripurl = tldextract.extract(slug)
    location = stripurl.domain + "." + stripurl.suffix
    stdlog("sharedutils: " + "checking for onion version - " + str(location))
    if len(stripurl.domain) == 16:
        stdlog("sharedutils: " + "v2 onionsite detected")
        version = 2
    elif len(stripurl.domain) == 56:
        stdlog("sharedutils: " + "v3 onionsite detected")
        version = 3
    else:
        stdlog("sharedutils: " + "unknown onion version, assuming clearnet")
        version = 0
    return version, location


def striptld(slug: str) -> str:
    """
    strips the tld from a url
    """
    # stripurl = tldextract.extract(slug)
    # return stripurl.domain
    parsed = urlparse(slug)
    scheme = "%s://" % parsed.scheme
    return parsed.geturl().replace(scheme, "", 1).replace("/", "-")


def createfile(slug: str) -> str:
    schema = urlsplit(slug)
    filename = schema.netloc + "".join(schema.path.split("/"))
    return "".join(filename.split("."))


def format_bytes(size: int) -> str:
    # 2**10 = 1024
    power = 2**10
    n = 0
    power_labels = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size > power:
        size /= power  # type: ignore[assignment]
        n += 1
    return f"{size:.2f} {power_labels[n]}"
