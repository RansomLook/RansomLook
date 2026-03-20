#!/usr/bin/env python3

import json
from typing import Any

from flask_restx import Namespace, Resource, fields  # type: ignore
from valkey import Valkey

from ransomlook.default import DB_RF, get_socket_path

api = Namespace("RecordedFutureAPI", description="Recorded Future integration API", path="/api/rf")

# ── Swagger models ──────────────────────────────────────────────────────

rf_leak_model = api.model(
    "RFLeak",
    {
        "name": fields.String(description="Channel / leak name"),
        "url": fields.String(description="Source URL"),
        "type": fields.String(description="Channel type"),
    },
)


@api.route("/leaks")
@api.doc(description="Return the list of all Recorded Future channel names.")
class RFLeaks(Resource):  # type: ignore[misc]
    @api.response(200, "List of channel names (strings)")  # type: ignore[untyped-decorator]
    def get(self) -> list[str]:
        leaks = []
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_RF)
        for key in red.keys():  # type: ignore[union-attr]
            leaks.append(key.decode())
        return leaks


@api.route("/leak/<string:name>")
@api.doc(description="Return details for a specific Recorded Future channel.", params={"name": "Channel name"})
class RFLeakinfo(Resource):  # type: ignore[misc]
    @api.response(200, "Channel details", rf_leak_model)  # type: ignore[untyped-decorator]
    @api.response(404, "Channel not found (returns {})")  # type: ignore[untyped-decorator]
    def get(self, name: str) -> Any:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_RF)
        leak = None
        leak = red.get(name.encode())
        if leak:
            return json.loads(leak)  # type: ignore[arg-type]
        return {}
