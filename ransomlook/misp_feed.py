#!/usr/bin/env python3
"""
Local MISP feed : one event per victim and one per group, stored in Valkey
(DB_MISP) and served on the fly under /feed/misp/. Subscribers pull, nothing is
pushed. Only public entities are exposed. UUIDs are deterministic (uuid5) so
they stay stable across updates ; the event timestamp is bumped on each refresh
so subscribers re-pull.
"""
import json
import time
import uuid as uuidlib
from typing import Any

import valkey
from pymisp import MISPEvent, MISPObject, MISPOrganisation

from .default import DB_GROUPS, DB_MISP, DB_POSTS
from .default.config import get_config, get_socket_path
from .misp import delete_event, push_event
from .sharedutils import errlog

# Fixed namespace for deterministic UUIDs. NEVER change this value.
NS = uuidlib.UUID("6f2b1e2a-9c3d-5a41-b7e8-0d1c2f3a4b5c")

MANIFEST_KEY = "misp:feed:manifest"  # hash: event_uuid -> manifest meta
EVENT_PREFIX = "misp:feed:event:"  # string: + event_uuid -> {"Event": ...}


def config() -> dict[str, Any]:
    """
    return the misp_feed configuration or an empty dict
    """
    try:
        return get_config("generic", "misp_feed") or {}
    except Exception:
        return {}


def enabled() -> bool:
    """
    check if the local misp feed is enabled
    """
    return bool(config().get("enable", False))


def push_enabled() -> bool:
    """
    check if pushing to a MISP instance is enabled
    """
    try:
        return bool(get_config("generic", "misp")["enable"])
    except Exception:
        return False


def getdb(db: int = DB_MISP) -> valkey.Valkey:
    """
    open a valkey connection on the given db
    """
    return valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=db)


def deterministic_uuid(key: str) -> str:
    """
    return a stable uuid5 for the given key
    """
    return str(uuidlib.uuid5(NS, key))


def siteurl() -> str:
    """
    return the configured site url without trailing slash
    """
    try:
        return (get_config("generic", "siteurl") or "").rstrip("/")
    except Exception:
        return ""


def organisation() -> MISPOrganisation:
    """
    build the creator organisation from the configuration
    """
    cfg = config()
    org = MISPOrganisation()
    org.name = cfg.get("orgc_name", "RansomLook")
    if cfg.get("orgc_uuid"):
        org.uuid = cfg["orgc_uuid"]
    return org


def baseevent(event_uuid: str, info: str, entrytype: str, galaxy: str | None) -> MISPEvent:
    """
    create a new event with the common feed metadata and tags
    """
    cfg = config()
    event = MISPEvent()
    event.uuid = event_uuid
    event.info = info
    event.distribution = int(cfg.get("distribution", 3))
    event.threat_level_id = int(cfg.get("threat_level_id", 4))
    event.analysis = int(cfg.get("analysis", 2))
    event.orgc = organisation()
    event.add_tag(cfg.get("tlp", "tlp:clear"))
    event.add_tag('ransomlook:type="' + entrytype + '"')
    if galaxy:
        event.add_tag('misp-galaxy:Ransomware="' + galaxy + '"')
    return event


def locationrole(location: dict[str, Any]) -> str:
    """
    map a location to its role for the infrastructure event
    """
    if location.get("admin"):
        return "Admin"
    if location.get("fs"):
        return "File Share"
    if location.get("chat"):
        return "Chat"
    if location.get("header"):
        return "Affiliates"
    return "DLS"


def victimevent(
    event_uuid: str,
    group: str,
    title: str,
    description: str | None,
    link: str | None,
    magnet: str | None,
    screen: str | None,
    galaxy: str | None,
) -> MISPEvent:
    """
    build the event describing a single victim
    """
    event = baseevent(event_uuid, group.title() + " — " + title, "victim", galaxy)

    misp_object = MISPObject("ransomware-group-post")
    misp_object.uuid = deterministic_uuid(event_uuid + "|obj")
    attribute = misp_object.add_attribute("title", title)
    attribute.uuid = deterministic_uuid(event_uuid + "|title")  # type: ignore[union-attr]
    attribute.to_ids = False  # type: ignore[union-attr]
    if description:
        attribute = misp_object.add_attribute("description", description)
        attribute.uuid = deterministic_uuid(event_uuid + "|description")  # type: ignore[union-attr]
        attribute.to_ids = False  # type: ignore[union-attr]
    event.add_object(misp_object)

    if link:
        attribute = event.add_attribute("link", link, comment="Leak page")
        attribute.uuid = deterministic_uuid(event_uuid + "|link")
        attribute.to_ids = False
    if magnet:
        attribute = event.add_attribute("link", magnet, comment="Magnet")
        attribute.uuid = deterministic_uuid(event_uuid + "|magnet")
        attribute.to_ids = False
    if screen:
        attribute = event.add_attribute("link", siteurl() + "/" + str(screen).lstrip("/"), comment="Screenshot")
        attribute.uuid = deterministic_uuid(event_uuid + "|screen")
        attribute.to_ids = False
    return event


def groupevent(event_uuid: str, group: str, locations: list[dict[str, Any]], galaxy: str | None) -> MISPEvent:
    """
    build the event describing the public infrastructure of a group
    """
    event = baseevent(event_uuid, group.title() + " — infrastructure", "infrastructure", galaxy)
    for location in locations:
        fqdn = location.get("fqdn")
        if not fqdn:
            continue
        comment = locationrole(location) + " — onion " + str(location.get("version") or "")
        comment += " — available=" + str(location.get("available"))
        attribute = event.add_attribute("domain", fqdn, comment=comment)
        attribute.uuid = deterministic_uuid(event_uuid + "|" + fqdn)
        attribute.to_ids = False
    return event


def store(event: MISPEvent, entrytype: str) -> None:
    """
    persist the event and its manifest entry, bumping the timestamp
    """
    cfg = config()
    timestamp = str(int(time.time()))
    event.timestamp = int(timestamp)  # bump so subscribers re-pull
    red = getdb()
    red.set(EVENT_PREFIX + event.uuid, json.dumps(event.to_feed()))
    meta = {
        "Orgc": {"name": cfg.get("orgc_name", "RansomLook"), "uuid": cfg.get("orgc_uuid", "")},
        "Tag": [{"name": cfg.get("tlp", "tlp:clear")}, {"name": 'ransomlook:type="' + entrytype + '"'}],
        "info": event.info,
        "date": str(event.date),
        "analysis": event.analysis,
        "threat_level_id": event.threat_level_id,
        "timestamp": timestamp,
    }
    red.hset(MANIFEST_KEY, event.uuid, json.dumps(meta))


def publish(event: MISPEvent, entrytype: str) -> None:
    """
    persist the event to the local feed and/or push it to the MISP instance.
    Both channels share the same event (same uuid).
    """
    if enabled():
        store(event, entrytype)
    if push_enabled():
        try:
            push_event(get_config("generic", "misp"), event)
        except Exception:
            errlog("misp_feed: can not push " + event.uuid)


def remove(event_uuid: str) -> None:
    """
    drop an event from the feed (entity turned private or deleted)
    """
    try:
        red = getdb()
        red.delete(EVENT_PREFIX + event_uuid)
        red.hdel(MANIFEST_KEY, event_uuid)
    except Exception:
        errlog("misp_feed: can not remove " + event_uuid)


def purge(event_uuid: str) -> None:
    """
    remove an event from the feed and, if push is enabled, from the MISP instance
    """
    remove(event_uuid)
    if push_enabled():
        try:
            delete_event(get_config("generic", "misp"), event_uuid)
        except Exception:
            errlog("misp_feed: can not delete " + event_uuid)


def remove_group(group_name: str) -> None:
    """
    purge a group's infrastructure event and all its victim events.
    Opt-in: only runs when misp_feed.remove_on_delete is true.
    """
    if not config().get("remove_on_delete", False):
        return
    try:
        purge(deterministic_uuid("infra|" + group_name))
        raw = getdb(DB_POSTS).get(group_name)
        if not raw:
            return
        for post in json.loads(raw):  # type: ignore[arg-type]
            title = post.get("post_title")
            if not title:
                continue
            event_uuid = post.get("misp_uuid") or deterministic_uuid("victim|" + group_name + "|" + title)
            purge(event_uuid)
    except Exception:
        errlog("misp_feed: can not remove group " + group_name)


def groupinfo(group_name: str) -> dict[str, Any] | None:
    """
    load a group record from DB_GROUPS
    """
    raw = getdb(DB_GROUPS).get(group_name)
    if not raw:
        return None
    return json.loads(raw)  # type: ignore[arg-type]


def refresh_victim(group_name: str, post_title: str) -> str | None:
    """
    (re)build the misp event for a single victim from the current state
    """
    if not (enabled() or push_enabled()):
        return None
    try:
        event_uuid = deterministic_uuid("victim|" + group_name + "|" + post_title)
        group = groupinfo(group_name)
        if group is not None and group.get("private"):
            remove(event_uuid)
            return None

        red = getdb(DB_POSTS)
        raw = red.get(group_name)
        if not raw:
            return None
        posts = json.loads(raw)  # type: ignore[arg-type]
        target = next((post for post in posts if post.get("post_title") == post_title), None)
        if target is None:
            return None

        if target.get("misp_uuid"):
            event_uuid = target["misp_uuid"]
        galaxy = group.get("ransomware_galaxy_value") if group else None
        event = victimevent(
            event_uuid,
            group_name,
            post_title,
            target.get("description"),
            target.get("link"),
            target.get("magnet"),
            target.get("screen"),
            galaxy or None,
        )
        event.date = str(target["discovered"]).split(" ")[0] if target.get("discovered") else event.date
        publish(event, "victim")

        if target.get("misp_uuid") != event_uuid:
            target["misp_uuid"] = event_uuid
            red.set(group_name, json.dumps(posts))
        return event_uuid
    except Exception:
        errlog("misp_feed: can not refresh victim " + group_name + " / " + post_title)
        return None


def refresh_group(group_name: str) -> str | None:
    """
    (re)build the infrastructure event for a group from its public locations
    """
    if not (enabled() or push_enabled()):
        return None
    try:
        event_uuid = deterministic_uuid("infra|" + group_name)
        group = groupinfo(group_name)
        if group is None or group.get("private"):
            remove(event_uuid)
            return None
        locations = [loc for loc in (group.get("locations") or []) if not loc.get("private")]
        if not locations:
            remove(event_uuid)
            return None
        event = groupevent(event_uuid, group_name, locations, group.get("ransomware_galaxy_value") or None)
        publish(event, "infrastructure")
        return event_uuid
    except Exception:
        errlog("misp_feed: can not refresh group " + group_name)
        return None


def manifest_json() -> str:
    """
    return the full feed manifest as a json string
    """
    entries = getdb().hgetall(MANIFEST_KEY) or {}
    manifest = {key.decode(): json.loads(value) for key, value in entries.items()}  # type: ignore[union-attr]
    return json.dumps(manifest)


def event_json(event_uuid: str) -> str | None:
    """
    return the raw event body as a json string, or None if unknown
    """
    raw = getdb().get(EVENT_PREFIX + event_uuid)
    return raw.decode() if raw else None  # type: ignore[union-attr]
