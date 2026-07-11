#!/usr/bin/env python3
"""
Local MISP feed : one event per victim, one per group / market infrastructure
and one per threat actor, stored in Valkey (DB_MISP) and served on the fly
under /feed/misp/. Subscribers pull, nothing is pushed. Only public entities
are exposed. UUIDs are deterministic (uuid5) so they stay stable across
updates ; the event timestamp is bumped on each refresh so subscribers re-pull.
"""
import json
import time
import uuid as uuidlib
from typing import Any
from urllib.parse import urljoin

import valkey
from pymisp import MISPEvent, MISPObject, MISPOrganisation

from .default import DB_ACTORS, DB_GROUPS, DB_MARKETS, DB_MISP, DB_POSTS
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
        event.add_tag('misp-galaxy:ransomware="' + galaxy + '"')
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


def group_base_url(group: dict[str, Any] | None) -> str:
    """
    return the base URL of the group's public DLS location, used to turn a post
    URI into the full claim URL. Prefer a plain DLS mirror over admin/fs/chat.
    """
    locations = (group or {}).get("locations") or []
    for location in locations:
        if location.get("private"):
            continue
        if location.get("admin") or location.get("fs") or location.get("chat") or location.get("header"):
            continue
        if location.get("slug"):
            return str(location["slug"])
    for location in locations:  # fall back to any public mirror
        if not location.get("private") and location.get("slug"):
            return str(location["slug"])
    return ""


def victimevent(
    event_uuid: str,
    group: str,
    title: str,
    description: str | None,
    link: str | None,
    magnet: str | None,
    screen: str | None,
    galaxy: str | None,
    base_url: str = "",
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
    if link:
        # "link" object relation = "Original URL location of the post" : store the
        # full claim URL (DLS base + URI), keeping an already-absolute link as-is.
        # link may be a bare int (legacy numeric post id) so coerce to str first.
        link = str(link)
        full_link = urljoin(base_url, link) if base_url else link
        attribute = misp_object.add_attribute("link", full_link, comment="Original URL location of the post")
        attribute.uuid = deterministic_uuid(event_uuid + "|link")  # type: ignore[union-attr]
        attribute.to_ids = False  # type: ignore[union-attr]
    if screen:
        # "proof" exists since template v5; explicit type so an older bundled
        # pymisp template does not reject the unknown object relation
        attribute = misp_object.add_attribute(
            "proof", siteurl() + "/" + str(screen).lstrip("/"), type="link", comment="Screenshot"
        )
        attribute.uuid = deterministic_uuid(event_uuid + "|screen")  # type: ignore[union-attr]
        attribute.to_ids = False  # type: ignore[union-attr]
    event.add_object(misp_object)

    if magnet:
        attribute = event.add_attribute("link", magnet, comment="Magnet")  # type: ignore[assignment]
        attribute.uuid = deterministic_uuid(event_uuid + "|magnet")  # type: ignore[union-attr]
        attribute.to_ids = False  # type: ignore[union-attr]
    return event


def addattr(event: MISPEvent, event_uuid: str, seed: str, misp_type: str, value: str, comment: str) -> None:
    """
    add a plain event attribute with a deterministic uuid
    """
    attribute = event.add_attribute(misp_type, value, comment=comment)
    attribute.uuid = deterministic_uuid(event_uuid + "|" + seed)  # type: ignore[union-attr]
    attribute.to_ids = False  # type: ignore[union-attr]


def groupevent(
    event_uuid: str,
    group: str,
    locations: list[dict[str, Any]],
    galaxy: str | None,
    entrytype: str = "infrastructure",
) -> MISPEvent:
    """
    build the event describing the public infrastructure of a group or market
    """
    event = baseevent(event_uuid, group.title() + " — " + entrytype, entrytype, galaxy)
    for location in locations:
        fqdn = location.get("fqdn")
        if not fqdn:
            continue
        comment = locationrole(location) + " — onion " + str(location.get("version") or "")
        comment += " — available=" + str(location.get("available"))
        attribute = event.add_attribute("domain", fqdn, comment=comment)
        attribute.uuid = deterministic_uuid(event_uuid + "|" + fqdn)  # type: ignore[union-attr]
        attribute.to_ids = False  # type: ignore[union-attr]
    return event


# actor contact channel -> (misp attribute type, comment)
CONTACT_TYPES = {
    "email": ("email", "Email"),
    "jabber": ("jabber-id", "Jabber"),
    "pgp": ("text", "PGP"),
    "matrix": ("text", "Matrix"),
    "session": ("text", "Session"),
    "telegram": ("text", "Telegram"),
    "tox": ("text", "Tox"),
    "simplex": ("text", "SimpleX"),
    "max": ("text", "MAX"),
    "sonar": ("text", "Sonar"),
    "x": ("text", "X / Twitter"),
    "bluesky": ("text", "Bluesky"),
}


def actorevent(event_uuid: str, actor: dict[str, Any]) -> MISPEvent:
    """
    build the event describing a threat actor profile
    """
    name = str(actor.get("name") or "")
    event = baseevent(event_uuid, name + " — threat actor", "actor", None)

    addattr(event, event_uuid, "name", "threat-actor", name, "Actor name")
    for alias in actor.get("aliases") or []:
        if alias:
            addattr(event, event_uuid, "alias|" + alias, "threat-actor", alias, "Alias")

    if actor.get("bio"):
        addattr(event, event_uuid, "bio", "text", str(actor["bio"]), "Bio")

    contacts = actor.get("contacts") or {}
    for channel, (misp_type, comment) in CONTACT_TYPES.items():
        for value in contacts.get(channel) or []:
            if value:
                addattr(event, event_uuid, "contact|" + channel + "|" + value, misp_type, value, comment)

    for source in actor.get("sources") or []:
        url = source.get("url") if isinstance(source, dict) else source
        if url:
            addattr(event, event_uuid, "source|" + url, "link", url, "Source")

    wanted = actor.get("wanted") or {}
    for org in ("fbi", "europol", "interpol"):
        url = (wanted.get(org) or {}).get("url")
        if url:
            addattr(event, event_uuid, "wanted|" + org, "link", url, org.upper() + " wanted notice")

    relations = actor.get("relations") or {}
    for group in relations.get("groups") or []:
        if group:
            addattr(event, event_uuid, "relation|group|" + group, "text", group, "Related group")
    for forum in relations.get("forums") or []:
        if forum:
            addattr(event, event_uuid, "relation|forum|" + forum, "text", forum, "Related market / forum")
    for peer in relations.get("peers") or []:
        peername = peer.get("name") if isinstance(peer, dict) else peer
        if peername:
            addattr(event, event_uuid, "relation|peer|" + peername, "text", peername, "Related actor")
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


def remove_market(market_name: str) -> None:
    """
    purge a market's infrastructure event and all its post events.
    Opt-in: only runs when misp_feed.remove_on_delete is true.
    """
    if not config().get("remove_on_delete", False):
        return
    try:
        purge(deterministic_uuid("market|" + market_name))
        raw = getdb(DB_POSTS).get(market_name)
        if not raw:
            return
        for post in json.loads(raw):  # type: ignore[arg-type]
            title = post.get("post_title")
            if not title:
                continue
            event_uuid = post.get("misp_uuid") or deterministic_uuid("victim|" + market_name + "|" + title)
            purge(event_uuid)
    except Exception:
        errlog("misp_feed: can not remove market " + market_name)


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
        # fall back to the group name as galaxy value when the group has no
        # ransomware-galaxy mapping, so the victim still gets a galaxy tag.
        galaxy = (group.get("ransomware_galaxy_value") if group else None) or group_name
        event = victimevent(
            event_uuid,
            group_name,
            post_title,
            target.get("description"),
            target.get("link"),
            target.get("magnet"),
            target.get("screen"),
            galaxy,
            group_base_url(group),
        )
        if target.get("discovered"):
            # the setter accepts a "YYYY-MM-DD" string even though the stub says date
            event.date = str(target["discovered"]).split(" ")[0]  # type: ignore[assignment]
        publish(event, "victim")

        if target.get("misp_uuid") != event_uuid:
            target["misp_uuid"] = event_uuid
            red.set(group_name, json.dumps(posts))
        return event_uuid
    except Exception as e:
        errlog("misp_feed: can not refresh victim " + group_name + " / " + post_title + " : " + repr(e))
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
        event = groupevent(event_uuid, group_name, locations, group.get("ransomware_galaxy_value") or group_name)
        publish(event, "infrastructure")
        return event_uuid
    except Exception:
        errlog("misp_feed: can not refresh group " + group_name)
        return None


def refresh_market(market_name: str) -> str | None:
    """
    (re)build the infrastructure event for a market / forum from its public locations
    """
    if not (enabled() or push_enabled()):
        return None
    try:
        event_uuid = deterministic_uuid("market|" + market_name)
        raw = getdb(DB_MARKETS).get(market_name)
        market = json.loads(raw) if raw else None  # type: ignore[arg-type]
        if market is None or market.get("private"):
            remove(event_uuid)
            return None
        locations = [loc for loc in (market.get("locations") or []) if not loc.get("private")]
        if not locations:
            remove(event_uuid)
            return None
        event = groupevent(event_uuid, market_name, locations, None, entrytype="market")
        publish(event, "market")
        return event_uuid
    except Exception:
        errlog("misp_feed: can not refresh market " + market_name)
        return None


def refresh_actor(actor_name: str) -> str | None:
    """
    (re)build the misp event for a threat actor profile
    """
    if not (enabled() or push_enabled()):
        return None
    try:
        key = actor_name.strip().lower()
        event_uuid = deterministic_uuid("actor|" + key)
        raw = getdb(DB_ACTORS).get(key)
        actor = json.loads(raw) if raw else None  # type: ignore[arg-type]
        if actor is None or actor.get("private"):
            remove(event_uuid)
            return None
        event = actorevent(event_uuid, actor)
        if actor.get("created_at"):
            # the setter accepts a "YYYY-MM-DD" string even though the stub says date
            event.date = str(actor["created_at"]).split("T")[0]  # type: ignore[assignment]
        publish(event, "actor")
        return event_uuid
    except Exception:
        errlog("misp_feed: can not refresh actor " + actor_name)
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
