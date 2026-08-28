#!/usr/bin/env python3
"""RaaS affiliate rules API.

Read-only: the blocks are authored from the admin interface. Visibility is
inherited from the group, exactly as on the web pages — a private group's rules
are absent for a caller without private access, and the group-scoped endpoint
answers 404 rather than an empty list so the two cases stay indistinguishable
from the outside.
"""
from typing import Any

from flask import request
from flask_restx import Namespace, Resource, fields  # type: ignore

from ransomlook import raas as raas_rules
from ransomlook.sharedutils import is_private_entity

api = Namespace("RaasAPI", description="Ransomware-as-a-Service affiliate rules", path="/api/raas-rules")


def _can_see_private() -> bool:
    """True when this caller may see private entities.

    Imported lazily and in one place: a second import of web.helpers in this
    file would make the first ignore comment go stale under mypy.
    """
    from web.helpers import viewer_can_see_private  # type: ignore[import-not-found]

    return bool(viewer_can_see_private(request))


# ── Swagger models ──────────────────────────────────────────────────────

raas_group_model = api.model(
    "RaasGroup",
    {
        "name": fields.String(description="Group name"),
        "blocks": fields.Integer(description="Number of recorded rule versions"),
        "latest": fields.String(description="Most recent start date, empty when none is dated"),
        "has_current": fields.Boolean(description="Whether one version is flagged as the current rules"),
    },
)

raas_block_model = api.model(
    "RaasBlock",
    {
        "id": fields.String(description="Block identifier"),
        "content": fields.String(description="Rules body, as Markdown source"),
        "comment": fields.String(description="Public editorial comment, may be empty"),
        "started": fields.String(description="Date the version came into force (YYYY-MM-DD), empty when unknown"),
        "current": fields.Boolean(description="Whether this is the set of rules in force"),
        "images": fields.List(fields.String, description="Screenshot URLs"),
        "created_at": fields.String(description="Creation timestamp"),
        "updated_at": fields.String(description="Last update timestamp"),
    },
)


def _payload(name: str, block: dict[str, Any]) -> dict[str, Any]:
    """One block as the API exposes it.

    Images are returned as URLs rather than bare filenames: the caller has no
    way to know the route, and the route is the only thing that enforces the
    privacy check on the files.
    """
    return {
        "id": block.get("id", ""),
        "content": block.get("content", ""),
        "comment": block.get("comment", ""),
        "started": block.get("started", ""),
        "current": block.get("current") is True,
        "images": [f"/raas-rules/{name}/asset/{image}" for image in (block.get("images") or [])],
        "created_at": block.get("created_at", ""),
        "updated_at": block.get("updated_at", ""),
    }


@api.route("/")
@api.doc(description="List the groups whose affiliate rules are recorded.")
class RaasIndex(Resource):  # type: ignore[misc]
    @api.marshal_list_with(raas_group_model)  # type: ignore[untyped-decorator]
    def get(self) -> list[dict[str, Any]]:
        include_private = _can_see_private()
        out = []
        for name in raas_rules.groups(include_private=include_private):
            blocks = raas_rules.load(name)
            if not blocks:
                continue
            out.append(
                {
                    "name": name,
                    "blocks": len(blocks),
                    "latest": raas_rules.latest_date(blocks),
                    "has_current": any(b.get("current") is True for b in blocks),
                }
            )
        return out


@api.route("/<string:name>")
@api.doc(
    description="Every recorded version of a group's affiliate rules, current first, then newest dated, then undated.",
    params={"name": "Group name"},
)
class RaasGroup(Resource):  # type: ignore[misc]
    @api.response(404, "Unknown group, or one this caller may not see")  # type: ignore[untyped-decorator]
    @api.marshal_list_with(raas_block_model)  # type: ignore[untyped-decorator]
    def get(self, name: str) -> list[dict[str, Any]]:
        key = raas_rules.norm_group(name)
        if not key:
            api.abort(404)
        if not _can_see_private() and is_private_entity(key):
            api.abort(404)
        blocks = raas_rules.sort_blocks(raas_rules.load(key))
        if not blocks:
            api.abort(404)
        return [_payload(key, block) for block in blocks]
