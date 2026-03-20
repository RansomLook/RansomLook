#!/usr/bin/env python3

import json
import os
from typing import Any

from flask_restx import Namespace, Resource, fields  # type: ignore
from valkey import Valkey

from ransomlook.default import DB_ACTORS, DB_GROUPS, DB_MARKETS, get_homedir, get_socket_path

api = Namespace("ActorsAPI", description="Threat actor intelligence API", path="/api/actors")

# ── Swagger models ──────────────────────────────────────────────────────

wanted_entry = api.model(
    "WantedEntry",
    {
        "url": fields.String(description="Wanted poster URL"),
    },
)

wanted_model = api.model(
    "Wanted",
    {
        "fbi": fields.Nested(wanted_entry, description="FBI wanted entry", skip_none=True),
        "europol": fields.Nested(wanted_entry, description="Europol wanted entry", skip_none=True),
        "interpol": fields.Nested(wanted_entry, description="Interpol wanted entry", skip_none=True),
    },
)

actor_summary_model = api.model(
    "ActorSummary",
    {
        "name": fields.String(description="Actor name"),
        "aliases": fields.List(fields.String, description="Known aliases"),
        "has_wanted": fields.Boolean(description="True if actor appears on any wanted list"),
    },
)

relations_model = api.model(
    "Relations",
    {
        "groups": fields.List(fields.String, description="Linked ransomware groups"),
        "forums": fields.List(fields.String, description="Linked markets / forums"),
        "peers": fields.List(fields.String, description="Known peer actors"),
    },
)

actor_detail_model = api.model(
    "ActorDetail",
    {
        "name": fields.String(description="Actor name"),
        "aliases": fields.List(fields.String, description="Known aliases"),
        "wanted": fields.Nested(wanted_model, description="Wanted list entries"),
        "contacts": fields.Raw(description="Contact channels (telegram, email, x, …)"),
        "profile": fields.List(fields.String, description="Profile links"),
        "relations": fields.Nested(relations_model, description="Relations to groups/forums/peers"),
        "rel_groups_known": fields.List(fields.String, description="Related groups that exist in DB"),
        "rel_groups_unknown": fields.List(fields.String, description="Related groups not found in DB"),
        "rel_forums_known": fields.List(fields.String, description="Related forums that exist in DB"),
        "rel_forums_unknown": fields.List(fields.String, description="Related forums not found in DB"),
        "peers_known": fields.List(fields.String, description="Peers that exist in DB"),
        "peers_unknown": fields.List(fields.String, description="Peers not found in DB"),
        "images": fields.List(fields.String, description="Image filenames in the actor logo directory"),
    },
)


def _exists_in(red: Valkey, name_lower: str) -> bool:
    for kk in red.keys():  # type: ignore[union-attr]
        if kk.decode().lower() == name_lower:
            return True
    return False


@api.route("/")
@api.doc(description="Return the list of all public threat actors with name, aliases and wanted status.")
class ActorsList(Resource):  # type: ignore[misc]
    @api.response(200, "List of actors", [actor_summary_model])  # type: ignore[untyped-decorator]
    def get(self) -> list[dict[str, Any]]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
        data = []
        for key in red.keys():  # type: ignore[union-attr]
            try:
                entry = json.loads(red.get(key))  # type: ignore[arg-type]
            except Exception:
                continue
            if entry.get("private"):
                continue
            entry["name"] = entry.get("name") or key.decode()
            entry["aliases"] = entry.get("aliases") or []
            entry["has_wanted"] = any(
                bool(entry.get("wanted", {}).get(k, {}).get("url")) for k in ("fbi", "europol", "interpol")
            )
            data.append(
                {
                    "name": entry["name"],
                    "aliases": entry["aliases"],
                    "has_wanted": entry["has_wanted"],
                }
            )
        data.sort(key=lambda x: x["name"].lower())
        return data


@api.route("/<string:name>")
@api.doc(
    description="Return full details for a threat actor including relations, wanted status and images.",
    params={"name": "Actor name (case-insensitive)"},
)
class ActorDetail(Resource):  # type: ignore[misc]
    @api.response(200, "Actor details", actor_detail_model)  # type: ignore[untyped-decorator]
    @api.response(404, "Actor not found or private")  # type: ignore[untyped-decorator]
    def get(self, name: str) -> dict[str, Any]:
        red_ta = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
        red_groups = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
        red_markets = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)

        target_key = None
        for k in red_ta.keys():  # type: ignore[union-attr]
            if k.decode().lower() == name.lower():
                target_key = k
                break
        if not target_key:
            api.abort(404, "Actor not found")

        try:
            actor = json.loads(red_ta.get(target_key))  # type: ignore[arg-type]
        except Exception:
            api.abort(404, "Actor not found")

        if actor.get("private"):
            api.abort(404, "Actor not found")

        actor["name"] = actor.get("name") or target_key.decode()  # type: ignore[union-attr]

        rel = actor.get("relations") or {}
        groups_list = rel.get("groups") or []
        forums_list = rel.get("forums") or []
        peers_raw = rel.get("peers") or []
        peer_names = [(p.get("name") if isinstance(p, dict) else str(p)) for p in peers_raw]

        rel_groups_known = [g for g in groups_list if _exists_in(red_groups, g.lower())]
        rel_groups_unknown = [g for g in groups_list if not _exists_in(red_groups, g.lower())]
        rel_forums_known = [f for f in forums_list if _exists_in(red_markets, f.lower())]
        rel_forums_unknown = [f for f in forums_list if not _exists_in(red_markets, f.lower())]
        peers_known = [p for p in peer_names if _exists_in(red_ta, (p or "").lower())]
        peers_unknown = [p for p in peer_names if p not in peers_known]

        images = []
        try:
            base_path = os.path.join(str(get_homedir()), "source", "logo", "actor", actor["name"])
            if os.path.isdir(base_path):
                for fn in sorted(os.listdir(base_path)):
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
                        images.append(fn)
        except Exception:
            pass

        return {
            "name": actor["name"],
            "aliases": actor.get("aliases") or [],
            "wanted": actor.get("wanted") or {},
            "contacts": actor.get("contacts") or {},
            "profile": actor.get("profile") or [],
            "relations": rel,
            "rel_groups_known": rel_groups_known,
            "rel_groups_unknown": rel_groups_unknown,
            "rel_forums_known": rel_forums_known,
            "rel_forums_unknown": rel_forums_unknown,
            "peers_known": peers_known,
            "peers_unknown": peers_unknown,
            "images": images,
        }
