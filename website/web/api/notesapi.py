#!/usr/bin/env python3

import json
import re
from typing import Any

from flask_restx import Namespace, Resource, fields  # type: ignore
from valkey import Valkey

from ransomlook.default import DB_NOTES, get_socket_path

api = Namespace("NotesAPI", description="Ransom notes API", path="/api/notes")

# ── Swagger models ──────────────────────────────────────────────────────

note_group_model = api.model(
    "NoteGroup",
    {
        "name": fields.String(description="Canonical group slug"),
        "aliases": fields.List(fields.String, description="Known aliases"),
    },
)

note_summary_model = api.model(
    "NoteSummary",
    {
        "id": fields.String(description="Note identifier (use with /api/notes/<id>)"),
        "name": fields.String(description="Note title"),
        "content": fields.String(description="Note content (plain text)"),
    },
)

note_model = api.model(
    "Note",
    {
        "id": fields.String(description="Note identifier"),
        "title": fields.String(description="Note title"),
        "content": fields.String(description="Note content (plain text)"),
        "format": fields.String(description="Content format (txt, md, …)"),
        "updated_at": fields.String(description="Last update timestamp"),
        "groups": fields.List(fields.String, description="Associated group names"),
    },
)


def _norm_group(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "-").replace("_", "-")
    s = re.sub(r"[^a-z0-9\-]+", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


@api.route("/")
@api.doc(description="Return the list of all groups that have associated ransom notes.")
class NoteGroups(Resource):  # type: ignore[misc]
    @api.response(200, "List of groups with notes", [note_group_model])  # type: ignore[untyped-decorator]
    def get(self) -> list[dict[str, Any]]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)

        found = set()
        cursor = 0
        while True:
            cursor, keys = red.scan(cursor=cursor, match="idx:group:*:notes", count=500)  # type: ignore[misc]
            for k in keys:
                k_dec = k.decode()
                parts = k_dec.split(":")
                if len(parts) >= 4 and red.scard(k) > 0:  # type: ignore[operator]
                    found.add(parts[2])
            if cursor == 0:
                break

        # Alias resolution
        alias_to_canon: dict[str, str] = {}
        raw_aliases = red.hgetall("alias:group") or {}
        for a, c in raw_aliases.items():  # type: ignore[union-attr]
            alias_to_canon[a.decode()] = c.decode()

        canon_to_aliases: dict[str, set[str]] = {}
        for alias, canon in alias_to_canon.items():
            canon_to_aliases.setdefault(canon, set()).add(alias)
        for c in list(found):
            als: set[bytes] = red.smembers(f"group:{c}:aliases") or set()  # type: ignore[assignment]
            if als:
                canon_to_aliases.setdefault(c, set()).update(x.decode() for x in als)

        canons = sorted({alias_to_canon.get(s, s) for s in found})

        data = []
        for canon in canons:
            data.append(
                {
                    "name": canon,
                    "aliases": sorted(list(canon_to_aliases.get(canon, set()))),
                }
            )
        return data


@api.route("/recent", "/recent/<int:number>")
@api.doc(
    description="Return the most recently added or updated ransom notes (default 50).",
    params={"number": "Number of notes to return (default 50)"},
)
class NotesRecent(Resource):  # type: ignore[misc]
    @api.response(200, "List of recent notes", [note_model])  # type: ignore[untyped-decorator]
    def get(self, number: int = 50) -> list[dict[str, Any]]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)
        ids = red.zrevrange("idx:notes:updated", 0, number - 1)
        if not ids:
            return []

        pipe = red.pipeline()
        for nid in ids:  # type: ignore[union-attr]
            pipe.get(f"note:{nid.decode()}")
        raw = pipe.execute()  # type: ignore[no-untyped-call]

        data = []
        for nid, b in zip(ids, raw):  # type: ignore[arg-type]
            if not b:
                continue
            try:
                n = json.loads(b)
            except Exception:
                continue
            data.append(
                {
                    "id": n.get("id") or nid.decode(),
                    "title": n.get("title") or "",
                    "content": n.get("content") or "",
                    "format": n.get("format") or "txt",
                    "updated_at": n.get("updated_at"),
                    "groups": n.get("groups", []),
                }
            )
        return data


@api.route("/group/<string:name>")
@api.doc(
    description="Return all ransom notes associated with a specific group.",
    params={"name": "Group name or alias (case-insensitive)"},
)
class NotesByGroup(Resource):  # type: ignore[misc]
    @api.response(200, "List of notes for this group", [note_summary_model])  # type: ignore[untyped-decorator]
    @api.response(404, "No notes found for this group")  # type: ignore[untyped-decorator]
    def get(self, name: str) -> list[dict[str, Any]]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)

        slug = _norm_group(name)
        mapped = red.hget("alias:group", slug)
        if mapped:
            slug = mapped.decode()  # type: ignore[union-attr]

        idset_keys = [f"idx:group:{slug}:notes"]
        try:
            aliases: set[bytes] = red.smembers(f"group:{slug}:aliases") or set()  # type: ignore[assignment]
            for a in aliases:
                idset_keys.append(f"idx:group:{a.decode()}:notes")
        except Exception:
            pass

        note_ids: set[str] = set()
        for k in idset_keys:
            try:
                for nid in red.smembers(k):  # type: ignore[union-attr]
                    note_ids.add(nid.decode())
            except Exception:
                pass

        if not note_ids:
            api.abort(404, "No notes found for this group")

        nid_list = sorted(note_ids)
        pipe = red.pipeline()
        for nid in nid_list:
            pipe.get(f"note:{nid}")
        raw = pipe.execute()  # type: ignore[no-untyped-call]

        data = []
        for nid, b in zip(nid_list, raw):
            if not b:
                continue
            try:
                n = json.loads(b)
                data.append(
                    {
                        "id": n.get("id") or nid,
                        "name": n.get("title", ""),
                        "content": n.get("content", ""),
                    }
                )
            except Exception:
                continue

        data.sort(key=lambda x: (x.get("name") or "").lower())
        return data


@api.route("/<string:note_id>")
@api.doc(description="Return full details for a specific ransom note.", params={"note_id": "Note identifier"})
class NoteDetail(Resource):  # type: ignore[misc]
    @api.response(200, "Note details", note_model)  # type: ignore[untyped-decorator]
    @api.response(404, "Note not found")  # type: ignore[untyped-decorator]
    def get(self, note_id: str) -> dict[str, Any]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)
        b = red.get(f"note:{note_id}")
        if not b:
            api.abort(404, "Note not found")
        try:
            n = json.loads(b)  # type: ignore[arg-type]
        except Exception:
            api.abort(500, "Malformed note data")
        return {
            "id": n.get("id"),
            "title": n.get("title") or "",
            "content": n.get("content") or "",
            "format": n.get("format") or "txt",
            "updated_at": n.get("updated_at"),
            "groups": n.get("groups", []),
        }
