#!/usr/bin/env python3
"""Swagger-documented endpoints for torrent swarm health + IP/ASN pivoting.

Migrated out of website/web/__init__.py so every route appears on /doc. The
implementations are thin wrappers around ransomlook.torrent_health and
ransomlook.ipenrich.
"""

from typing import Any

from flask import jsonify, request
from flask_restx import Namespace, Resource, fields  # type: ignore


api = Namespace("TorrentHealth", description="Torrent swarm health, peer enrichment and IP/ASN pivot", path="/api/torrent")


def _private_names() -> set[str]:
    """Group/market names this caller must not see in a torrent payload.

    Every route in this namespace is unauthenticated, and a swarm entry carries
    the names of the groups it belongs to. Returns an empty set — a no-op for
    the redactor — when the caller is entitled to private entries.
    """
    from ransomlook.sharedutils import get_private_entity_names
    from web.helpers import viewer_can_see_private  # type: ignore[import-not-found]

    if viewer_can_see_private(request):
        return set()
    return get_private_entity_names()


# ── Swagger models ──────────────────────────────────────────────────────

top_ip_model = api.model("TopIp", {
    "ip": fields.String(description="Peer IP address"),
    "count": fields.Integer(description="Number of scan appearances"),
    "torrents": fields.Integer(description="Number of distinct torrents"),
    "seed_torrents": fields.Integer(description="Number of torrents where this IP seeded"),
})

top_asn_model = api.model("TopAsn", {
    "asn": fields.String(description="Autonomous System Number"),
    "ips": fields.Integer(description="Distinct IPs observed for this ASN"),
    "torrents": fields.Integer(description="Distinct torrents observed with an IP from this ASN"),
    "seed_torrents": fields.Integer(description="Torrents where at least one IP from this ASN seeded"),
})

cross_group_model = api.model("CrossGroupIp", {
    "ip": fields.String(),
    "group_count": fields.Integer(description="Number of ransomware groups this IP touched"),
    "groups": fields.List(fields.String()),
    "torrents": fields.Integer(),
    "seed_torrents": fields.Integer(),
})


# ── /api/torrent/health ──────────────────────────────────────────────────


@api.route("/health")
@api.doc(description="Paginated list of tracked swarms with last known state.",
         params={"page": "Page number (default 1).",
                 "per_page": "Items per page (1-200, default 50).",
                 "alive": "When 1, only include swarms with peers>0. Default 0 (all swarms).",
                 "q": "Substring match against infohash, name, groups. Default: no filter."})
class HealthList(Resource):  # type: ignore[misc]
    def get(self) -> Any:
        from ransomlook import torrent_health as th
        try:
            page = max(1, int(request.args.get("page", "1")))
        except ValueError:
            page = 1
        try:
            per_page = min(200, max(1, int(request.args.get("per_page", "50"))))
        except ValueError:
            per_page = 50
        alive_only = request.args.get("alive") == "1"
        query = (request.args.get("q") or "").strip().lower()

        rows = []
        for ih in th.list_infohashes():
            meta = th.get_meta(ih)
            if not meta:
                continue
            if alive_only and int(meta.get("last_peers_count") or 0) == 0:
                continue
            if query:
                hay = " ".join([
                    ih.lower(),
                    (meta.get("name") or "").lower(),
                    " ".join(meta.get("groups") or []).lower(),
                ])
                if query not in hay:
                    continue
            rows.append(meta)
        rows = [r for r in th.redact_private_groups(rows, _private_names()) if r]
        rows.sort(key=lambda r: (-int(r.get("last_peers_count") or 0), r.get("name") or ""))
        total = len(rows)
        start = (page - 1) * per_page
        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "results": rows[start:start + per_page],
        })


@api.route("/health/<string:infohash>")
@api.doc(description="Full metadata + historic scans for one infohash.",
         params={"infohash": "SHA-1 or SHA-256 infohash.",
                 "history": "Number of historic scans to return (1-200, default 50)."})
class HealthDetail(Resource):  # type: ignore[misc]
    def get(self, infohash: str) -> Any:
        from ransomlook import torrent_health as th
        meta = th.redact_private_groups(th.get_meta(infohash), _private_names())
        if not meta:
            # also covers a swarm whose only links were to private entities
            return {"error": "unknown infohash"}, 404
        try:
            limit = min(200, max(1, int(request.args.get("history", "50"))))
        except ValueError:
            limit = 50
        history = th.get_history(infohash, limit=limit)
        return jsonify({"meta": meta, "history": history})


# Refresh endpoint stays as a plain @app.route (background-thread logic with
# rate-limit + running-lock) in website/web/__init__.py; not worth duplicating
# the threading dance here. It is still reachable at POST /api/torrent/refresh/<ih>.


# ── /api/torrent/top/* ───────────────────────────────────────────────────


@api.route("/top/ips")
@api.doc(description="Top IPs by scan appearances. Optionally restrict to the last N days.",
         params={"limit": "Max rows (1-500, default 50).",
                 "seed_only": "1 = rank by seeder appearances only. Default 0.",
                 "days": "Time window in days. 0 or omitted = all time (default).",
                 "format": "Response format: 'json' (default) or 'csv'."})
class TopIps(Resource):  # type: ignore[misc]
    @api.response(200, "Top IPs", [top_ip_model])  # type: ignore[untyped-decorator]
    def get(self) -> Any:
        from ransomlook import torrent_health as th
        try:
            limit = min(500, max(1, int(request.args.get("limit", "50"))))
        except ValueError:
            limit = 50
        seed_only = request.args.get("seed_only") == "1"
        try:
            days = int(request.args.get("days") or 0)
        except ValueError:
            days = 0
        if days > 0:
            results = th.get_top_ips_windowed(limit=limit, seed_only=seed_only, days=days)
        else:
            results = th.get_top_ips(limit=limit, seed_only=seed_only)
        return _csv_or_json({"results": results}, request.args.get("format"), "top_ips.csv")


@api.route("/top/asn")
@api.doc(description="Top ASNs by distinct IPs observed on tracked swarms.",
         params={"limit": "Max rows (1-500, default 50).",
                 "seed_only": "1 = rank by seeder IPs only. Default 0.",
                 "days": "Time window in days. 0 or omitted = all time (default).",
                 "format": "Response format: 'json' (default) or 'csv'."})
class TopAsn(Resource):  # type: ignore[misc]
    @api.response(200, "Top ASNs", [top_asn_model])  # type: ignore[untyped-decorator]
    def get(self) -> Any:
        from ransomlook import torrent_health as th
        try:
            limit = min(500, max(1, int(request.args.get("limit", "50"))))
        except ValueError:
            limit = 50
        seed_only = request.args.get("seed_only") == "1"
        try:
            days = int(request.args.get("days") or 0)
        except ValueError:
            days = 0
        if days > 0:
            results = th.get_top_asn_windowed(limit=limit, seed_only=seed_only, days=days)
        else:
            results = th.get_top_asn(limit=limit, seed_only=seed_only)
        return _csv_or_json({"results": results}, request.args.get("format"), "top_asn.csv")


@api.route("/top/cross-group")
@api.doc(description="IPs observed seeding/leeching for 2+ distinct ransomware groups.",
         params={"limit": "Max rows (1-500, default 50).",
                 "format": "Response format: 'json' (default) or 'csv'."})
class TopCrossGroup(Resource):  # type: ignore[misc]
    @api.response(200, "IPs spanning multiple groups", [cross_group_model])  # type: ignore[untyped-decorator]
    def get(self) -> Any:
        from ransomlook import torrent_health as th
        try:
            limit = min(500, max(1, int(request.args.get("limit", "50"))))
        except ValueError:
            limit = 50
        results = [
            r for r in th.redact_private_groups(th.get_top_cross_group_ips(limit=limit), _private_names())
            if r and int(r.get("group_count") or 0) >= 2
        ]
        return _csv_or_json({"results": results}, request.args.get("format"), "cross_group.csv")


# ── /api/torrent/ip/<ip> ─────────────────────────────────────────────────


@api.route("/ip/<string:ip>")
@api.doc(description="Everything known about an IP: torrent associations, enrichment, group span.",
         params={"ip": "Peer IP address.",
                 "format": "Response format: 'json' (default) or 'csv'."})
class IpDetail(Resource):  # type: ignore[misc]
    def get(self, ip: str) -> Any:
        from ransomlook import torrent_health as th
        detail = th.redact_private_groups(th.get_ip_detail(ip.strip()), _private_names())
        if not detail.get("torrents") and not detail.get("enrichment"):
            return detail, 404
        return _csv_or_json(detail, request.args.get("format"), f"ip_{ip}.csv", csv_field="torrents")


@api.route("/ip/<string:ip>/timeline")
@api.doc(description="Daily observation counts over the last N days.",
         params={"ip": "Peer IP address.",
                 "days": "Time window in days (1-90, default 30)."})
class IpTimeline(Resource):  # type: ignore[misc]
    def get(self, ip: str) -> Any:
        from ransomlook import torrent_health as th
        try:
            days = min(90, max(1, int(request.args.get("days", "30"))))
        except ValueError:
            days = 30
        return jsonify({"ip": ip, "days": days, "series": th.get_ip_timeline(ip.strip(), days=days)})


# ── /api/torrent/asn/<asn> ───────────────────────────────────────────────


@api.route("/asn/<string:asn>")
@api.doc(description="Everything known about an ASN: IPs and torrents observed.",
         params={"asn": "Autonomous System Number (with or without AS prefix).",
                 "format": "Response format: 'json' (default) or 'csv'."})
class AsnDetail(Resource):  # type: ignore[misc]
    def get(self, asn: str) -> Any:
        from ransomlook import torrent_health as th
        detail = th.redact_private_groups(th.get_asn_detail(asn.strip()), _private_names())
        if not detail.get("ips") and not detail.get("torrents"):
            return detail, 404
        return _csv_or_json(detail, request.args.get("format"), f"asn_{asn}.csv", csv_field="torrents")


# ── CSV helper ───────────────────────────────────────────────────────────


def _csv_or_json(data: Any, fmt: str | None, filename: str, csv_field: str = "results") -> Any:
    """Either return JSON (default) or a CSV download when fmt=='csv'."""
    import csv
    import io
    from flask import Response

    if fmt != "csv":
        return jsonify(data)
    rows = data.get(csv_field, []) if isinstance(data, dict) else []
    if not rows:
        return Response("\n", mimetype="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    # Flatten list/set fields (groups, …) into semicolon-joined strings.
    def flatten(v: Any) -> Any:
        if isinstance(v, (list, tuple, set)):
            return ";".join(str(x) for x in v)
        return v

    cols = list(rows[0].keys())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([flatten(r.get(c, "")) for c in cols])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
