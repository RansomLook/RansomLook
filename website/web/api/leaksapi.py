#!/usr/bin/env python3

import json
from typing import Any

from flask_restx import Namespace, Resource, fields  # type: ignore
from valkey import Valkey

from ransomlook.default import DB_LEAKS, get_socket_path

api = Namespace("LeaksAPI", description="Data breach / leak database API", path="/api/leaks")

# ── Swagger models ──────────────────────────────────────────────────────

leak_summary_model = api.model(
    "LeakSummary",
    {
        "id": fields.Integer(description="Numeric breach identifier"),
        "name": fields.String(description="Breach name"),
    },
)

leak_detail_model = api.model(
    "LeakDetail",
    {
        "name": fields.String(description="Breach name"),
        "columns": fields.List(fields.String, description="Column names exposed"),
        "records": fields.Integer(description="Number of records"),
        "domain": fields.String(description="Affected domain"),
        "date": fields.String(description="Breach date"),
        "description": fields.String(description="Breach description"),
    },
)


@api.route("/leaks")
@api.doc(description="Return the list of all known data breaches (id and name).")
class Leaks(Resource):  # type: ignore[misc]
    @api.response(200, "List of breaches", [leak_summary_model])  # type: ignore[untyped-decorator]
    def get(self) -> list[dict[str, Any]]:
        leaks = []
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)
        for key in red.keys():  # type: ignore[union-attr]
            leak = {}
            leak["id"] = int(key.decode())
            leak["name"] = json.loads(red.get(key))["name"]  # type: ignore[arg-type]
            leaks.append(leak)
        return sorted(leaks, key=lambda x: x["id"])


@api.route("/leaks/<string:id>")
@api.doc(description="Return full details for a specific breach.", params={"id": "Numeric breach identifier"})
class LeaksDetails(Resource):  # type: ignore[misc]
    @api.response(200, "Breach details", leak_detail_model)  # type: ignore[untyped-decorator]
    @api.response(404, "Breach not found")  # type: ignore[untyped-decorator]
    def get(self, id: str) -> dict[str, Any]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)
        data = red.get(id)
        if data is None:
            api.abort(404, "Breach not found")
        return json.loads(data)  # type: ignore[arg-type]
