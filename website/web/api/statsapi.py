#!/usr/bin/env python3

import json
from datetime import datetime, timedelta
from typing import Any

from dateutil import parser as dateutil_parser
from flask import request
from flask_restx import Namespace, Resource, fields  # type: ignore
from valkey import Valkey

from ransomlook.default import (
    DB_GROUPS,
    DB_HEALTH,
    DB_LEAKS,
    DB_MARKETS,
    DB_NOTES,
    DB_POSTS,
    get_socket_path,
)
from ransomlook.sharedutils import (
    currentmonthstr,
    get_private_entity_names,
    groupcount,
    hostcount,
    hostcountadmin,
    hostcountchat,
    hostcountdls,
    hostcountfs,
    mounthlypostcount,
    onlinecount,
    parsercount,
    postcount,
    postslast24h,
    postssince,
    poststhisyear,
)

api = Namespace("StatsAPI", description="Statistics, trending and search API", path="/api")

# ── Swagger models ──────────────────────────────────────────────────────

stats_model = api.model(
    "Stats",
    {
        "groups": fields.Integer(description="Total number of groups"),
        "groups_locations": fields.Integer(description="Total group locations (unique FQDNs)"),
        "groups_dls": fields.Integer(description="DLS (leak site) mirrors"),
        "groups_fs": fields.Integer(description="File server mirrors"),
        "groups_chat": fields.Integer(description="Chat mirrors"),
        "groups_admin": fields.Integer(description="Admin panel mirrors"),
        "groups_online": fields.Integer(description="Currently reachable group mirrors"),
        "markets": fields.Integer(description="Total number of markets / forums"),
        "markets_locations": fields.Integer(description="Total market locations"),
        "markets_online": fields.Integer(description="Currently reachable market mirrors"),
        "posts_total": fields.Integer(description="Total posts across all time"),
        "posts_24h": fields.Integer(description="Posts discovered in the last 24 hours"),
        "posts_month": fields.Integer(description="Posts discovered this month"),
        "posts_month_label": fields.String(description="Current month name"),
        "posts_90d": fields.Integer(description="Posts in the last 90 days"),
        "posts_year": fields.Integer(description="Posts this year"),
        "year": fields.Integer(description="Current year"),
        "parsers": fields.Integer(description="Number of active parsers"),
    },
)

hot_entry_model = api.model(
    "HotEntry",
    {
        "group": fields.String(description="Group name (lowercase)"),
        "count": fields.Integer(description="Number of posts in the period"),
        "last_post": fields.String(description="Most recent post timestamp"),
    },
)

hot_response_model = api.model(
    "HotResponse",
    {
        "days": fields.Integer(description="Number of days in the window"),
        "from_date": fields.String(description="Start date (YYYY-MM-DD)"),
        "total_posts": fields.Integer(description="Total posts in the window"),
        "rows": fields.List(fields.Nested(hot_entry_model)),
    },
)

search_result_model = api.model(
    "SearchResult",
    {
        "groups": fields.List(fields.Raw, description="Matching groups"),
        "markets": fields.List(fields.Raw, description="Matching markets / forums"),
        "posts": fields.List(fields.Raw, description="Matching posts"),
        "leaks": fields.List(fields.Raw, description="Matching data breaches"),
        "notes": fields.List(fields.Raw, description="Matching ransom notes"),
    },
)

health_entry_model = api.model(
    "HealthEntry",
    {
        "slug": fields.String(description="Mirror URL"),
        "uptime_30d": fields.Integer(description="Uptime percentage over last 30 days"),
        "series": fields.List(fields.Integer, description="Daily availability (0/1) for up to 90 days"),
    },
)


# ── /api/stats ───────────────────────────────────────────────────────────


@api.route("/stats")
@api.doc(description="Return aggregated platform statistics (group/market counts, post counts, mirror status).")
class StatsEndpoint(Resource):  # type: ignore[misc]
    @api.response(200, "Platform statistics", stats_model)  # type: ignore[untyped-decorator]
    def get(self) -> dict[str, Any]:
        return {
            "groups": groupcount(DB_GROUPS),
            "groups_locations": hostcount(DB_GROUPS),
            "groups_dls": hostcountdls(DB_GROUPS),
            "groups_fs": hostcountfs(DB_GROUPS),
            "groups_chat": hostcountchat(DB_GROUPS),
            "groups_admin": hostcountadmin(DB_GROUPS),
            "groups_online": onlinecount(DB_GROUPS),
            "markets": groupcount(DB_MARKETS),
            "markets_locations": hostcount(DB_MARKETS),
            "markets_online": onlinecount(DB_MARKETS),
            "posts_total": postcount(),
            "posts_24h": postslast24h(),
            "posts_month": mounthlypostcount(),
            "posts_month_label": currentmonthstr(),
            "posts_90d": postssince(90),
            "posts_year": poststhisyear(),
            "year": datetime.now().year,
            "parsers": parsercount(),
        }


# ── /api/hot ─────────────────────────────────────────────────────────────


@api.route("/hot", "/hot/<int:days>")
@api.doc(
    description="Return groups ranked by post activity over the last N days (default 7, max 365).",
    params={"days": "Number of days to look back (1-365, default 7)"},
)
class HotEndpoint(Resource):  # type: ignore[misc]
    @api.response(200, "Trending groups", hot_response_model)  # type: ignore[untyped-decorator]
    def get(self, days: int = 7) -> dict[str, Any]:
        if days < 1:
            days = 1
        if days > 365:
            days = 365

        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        actualdate = datetime.now() + timedelta(days=-days)
        private_names = get_private_entity_names()

        posts = []
        for key in red.keys():  # type: ignore[union-attr]
            group_name = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
            if group_name.lower() in private_names:
                continue
            try:
                entries = json.loads(red.get(key))  # type: ignore[arg-type]
            except Exception:
                continue
            for entry in entries:
                dt_obj = None
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        dt_obj = datetime.strptime(entry.get("discovered", ""), fmt)
                        break
                    except Exception:
                        pass
                if not dt_obj:
                    continue
                if dt_obj > actualdate:
                    e = dict(entry)
                    e["group_name"] = group_name
                    posts.append(e)

        by_group: dict[str, dict[str, Any]] = {}
        for p in posts:
            g = p.get("group_name", "").lower()
            if g not in by_group:
                by_group[g] = {"group": g, "count": 0, "last_post": None}
            by_group[g]["count"] += 1
            dp = p.get("discovered")
            if dp:
                by_group[g]["last_post"] = max(by_group[g]["last_post"], dp) if by_group[g]["last_post"] else dp

        rows = sorted(by_group.values(), key=lambda x: (x["count"], x["last_post"] or ""), reverse=True)

        return {
            "days": days,
            "from_date": actualdate.strftime("%Y-%m-%d"),
            "total_posts": len(posts),
            "rows": rows,
        }


# ── /api/search ──────────────────────────────────────────────────────────


@api.route("/search")
@api.doc(
    description="Search across groups, markets, posts, data breaches and ransom notes.",
    params={"q": "Search query (required, min 2 characters)"},
)
class SearchEndpoint(Resource):  # type: ignore[misc]
    @api.response(200, "Search results", search_result_model)  # type: ignore[untyped-decorator]
    @api.response(400, "Missing or too short query")  # type: ignore[untyped-decorator]
    def get(self) -> dict[str, Any]:
        query = (request.args.get("q") or "").strip()
        if len(query) < 2:
            api.abort(400, "Query must be at least 2 characters")

        ql = query.lower()

        # Groups (DB=0)
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
        groups = []
        for key in red.keys():  # type: ignore[union-attr]
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if group.get("private"):
                continue
            name = key.decode()
            meta = group.get("meta") or ""
            if ql in name.lower() or ql in meta.lower():
                groups.append({"name": name, "meta": meta})
        groups.sort(key=lambda x: x["name"].lower())

        # Markets (DB=3)
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
        markets = []
        for key in red.keys():  # type: ignore[union-attr]
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if group.get("private"):
                continue
            name = key.decode()
            meta = group.get("meta") or ""
            if ql in name.lower() or ql in meta.lower():
                markets.append({"name": name, "meta": meta})
        markets.sort(key=lambda x: x["name"].lower())

        # Posts (DB=2)
        private_names = get_private_entity_names()
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        found_posts = []
        for key in red.keys():  # type: ignore[union-attr]
            group_name = key.decode()
            if group_name.lower() in private_names:
                continue
            entries = json.loads(red.get(key))  # type: ignore[arg-type]
            for entry in entries:
                title = (entry.get("post_title") or "").lower()
                desc = (entry.get("description") or "").lower()
                if ql in title or ql in desc:
                    entry["group_name"] = group_name
                    found_posts.append(entry)
        found_posts.sort(key=lambda x: x.get("discovered", ""), reverse=True)

        # Leaks (DB=4)
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)
        leaks = []
        for key in red.keys():  # type: ignore[union-attr]
            leak = json.loads(red.get(key))  # type: ignore[arg-type]
            if ql in (leak.get("name") or "").lower():
                leak["key"] = key.decode()
                leaks.append(leak)
        leaks.sort(key=lambda x: (x.get("name") or "").lower())

        # Notes (DB=11)
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)
        notes = []
        try:
            ids = [i.decode() for i in red.zrevrange("idx:notes:updated", 0, -1)]  # type: ignore[union-attr]
            ids = ids[:2000]
            pipe = red.pipeline()
            for nid in ids:
                pipe.get(f"note:{nid}")
            raw = pipe.execute()  # type: ignore[no-untyped-call]
            for b in raw:
                if not b:
                    continue
                try:
                    n = json.loads(b)
                except Exception:
                    continue
                title = (n.get("title") or "").lower()
                content = (n.get("content") or "").lower()
                if ql in title or ql in content:
                    notes.append(
                        {
                            "group_name": (n.get("groups") or [""])[0],
                            "name": n.get("title", ""),
                            "content": n.get("content", ""),
                        }
                    )
        except Exception:
            pass
        notes.sort(key=lambda x: (x.get("group_name") or "").lower())

        return {
            "groups": groups,
            "markets": markets,
            "posts": found_posts,
            "leaks": leaks,
            "notes": notes,
        }


# ── /api/health ──────────────────────────────────────────────────────────


@api.route("/health/<string:name>")
@api.doc(
    description="Return 30-day uptime percentage and daily availability series for all mirrors of a group or market.",
    params={"name": "Group or market name (case-insensitive)"},
)
class HealthEndpoint(Resource):  # type: ignore[misc]
    @api.response(200, "Mirror health data", [health_entry_model])  # type: ignore[untyped-decorator]
    @api.response(404, "No health data found")  # type: ignore[untyped-decorator]
    def get(self, name: str) -> list[dict[str, Any]]:
        red6 = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_HEALTH)

        # Resolve actual group name (case-sensitive in Redis keys)
        real_name = None
        for db_num in (DB_GROUPS, DB_MARKETS):
            red_tmp = Valkey(unix_socket_path=get_socket_path("cache"), db=db_num)
            for k in red_tmp.keys():  # type: ignore[union-attr]
                if k.decode().lower() == name.lower():
                    entry_raw = red_tmp.get(k)
                    if entry_raw:
                        try:
                            entry_data = json.loads(entry_raw)  # type: ignore[arg-type]
                            if entry_data.get("private") is True:
                                api.abort(404, "No health data found for this group")
                        except ValueError:
                            pass
                    real_name = k.decode()
                    break
            if real_name:
                break
        if not real_name:
            real_name = name  # fallback to provided name

        results = []
        cursor = 0
        while True:
            cursor, keys = red6.scan(cursor=cursor, match=f"health:{real_name}:*", count=500)  # type: ignore[misc]
            for k in keys:
                k_dec = k.decode()
                # Skip counter/lastday keys
                if ":cnt:" in k_dec or ":lastday:" in k_dec:
                    continue
                parts = k_dec.split(":", 2)  # health:<group>:<slug>
                if len(parts) < 3:
                    continue
                slug = parts[2]
                raw = red6.get(k)
                if not raw:
                    continue
                try:
                    series = json.loads(raw)  # type: ignore[arg-type]
                except Exception:
                    continue
                last_30 = series[-30:] if len(series) >= 30 else series
                uptime = round(100 * sum(last_30) / max(len(last_30), 1))
                results.append(
                    {
                        "slug": slug,
                        "uptime_30d": uptime,
                        "series": series,
                    }
                )
            if cursor == 0:
                break

        if not results:
            api.abort(404, "No health data found for this group")

        results.sort(key=lambda x: x["slug"])
        return results


# ── /api/compare ─────────────────────────────────────────────────────────

compare_entry_model = api.model(
    "CompareEntry",
    {
        "name": fields.String(description="Group or market name"),
        "posts7": fields.Integer(description="Posts in the last 7 days"),
        "posts30": fields.Integer(description="Posts in the last 30 days"),
        "posts365": fields.Integer(description="Posts in the last 365 days"),
        "mirrors_total": fields.Integer(description="Total visible mirrors"),
        "mirrors_up": fields.Integer(description="Currently reachable mirrors"),
        "captcha": fields.Boolean(description="Uses captcha"),
        "raas": fields.Boolean(description="Ransomware-as-a-Service"),
        "uptime30": fields.Integer(description="Average 30-day uptime percentage (null if no data)"),
    },
)

compare_response_model = api.model(
    "CompareResponse",
    {
        "kind": fields.String(description="Entity type (group or market)"),
        "a": fields.Nested(compare_entry_model, description="First entity", skip_none=True),
        "b": fields.Nested(compare_entry_model, description="Second entity", skip_none=True),
    },
)


def _resolve_key(red: Valkey, name: str) -> Any:
    """Case-insensitive key lookup, returns (redis_key, decoded_name) or (None, None)."""
    for k in red.keys():  # type: ignore[union-attr]
        if k.decode().lower() == name.lower():
            return k, k.decode()
    return None, None


def _posts_in_window(red_posts: Valkey, key: Any, days: int) -> int:
    if not key or key not in red_posts.keys():  # type: ignore[operator]
        return 0
    try:
        posts = json.loads(red_posts.get(key))  # type: ignore[arg-type]
    except Exception:
        return 0
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    count = 0
    for p in posts:
        ts = p.get("discovered") or p.get("timestamp") or p.get("time")
        d = None
        if isinstance(ts, str):
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    d = datetime.strptime(ts, fmt)
                    break
                except Exception:
                    pass
        if d is None and ts:
            try:
                d = dateutil_parser.parse(ts)
            except Exception:
                pass
        if d and d > cutoff:
            count += 1
    return count


def _avg_uptime30(red_health: Valkey, entry_name: str, locations: list[Any]) -> int | None:
    vals = []
    for loc in locations:
        slug = (loc.get("slug") or "").strip()
        if not slug:
            continue
        raw = red_health.get(f"health:{entry_name}:{slug}")
        if not raw:
            continue
        try:
            series = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            continue
        if not isinstance(series, list) or not series:
            continue
        last = series[-30:]
        norm = [1 if x in (1, True, "1") else 0 for x in last]
        if norm:
            vals.append(sum(norm) / len(norm))
    return round(100 * sum(vals) / len(vals)) if vals else None


def _compute_entry(kind: str, name: str) -> dict[str, Any] | None:
    db_num = DB_GROUPS if kind == "group" else DB_MARKETS
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=db_num)
    red_posts = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)

    key, real_name = _resolve_key(red, name)
    if not key:
        return None

    try:
        entry = json.loads(red.get(key))  # type: ignore[arg-type]
    except Exception:
        return None

    if entry.get("private") is True:
        return None

    entry["name"] = entry.get("name") or real_name
    locs = entry.get("locations") or []
    locs = [l for l in locs if not l.get("private")]
    visible = [l for l in locs if not l.get("fs") and not l.get("chat") and not l.get("admin")] or locs

    try:
        red_health = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_HEALTH)
    except Exception:
        red_health = None

    return {
        "name": entry["name"],
        "posts7": _posts_in_window(red_posts, key, 7),
        "posts30": _posts_in_window(red_posts, key, 30),
        "posts365": _posts_in_window(red_posts, key, 365),
        "mirrors_total": len(visible),
        "mirrors_up": sum(1 for l in visible if l.get("available") in (True, 1, "1")),
        "captcha": entry.get("captcha", False),
        "raas": entry.get("raas", False),
        "uptime30": _avg_uptime30(red_health, entry["name"], visible) if red_health else None,
    }


@api.route("/compare")
@api.doc(
    description="Compare two groups or markets side by side (post activity, mirrors, uptime, captcha, RaaS).",
    params={
        "kind": 'Entity type: "group" or "market" (default: group)',
        "a": "First entity name (required)",
        "b": "Second entity name (required)",
    },
)
class CompareEndpoint(Resource):  # type: ignore[misc]
    @api.response(200, "Comparison result", compare_response_model)  # type: ignore[untyped-decorator]
    @api.response(400, "Missing parameters")  # type: ignore[untyped-decorator]
    @api.response(404, "One or both entities not found")  # type: ignore[untyped-decorator]
    def get(self) -> dict[str, Any]:
        kind = (request.args.get("kind") or "group").strip().lower()
        if kind not in ("group", "market"):
            kind = "group"

        name_a = (request.args.get("a") or "").strip()
        name_b = (request.args.get("b") or "").strip()

        if not name_a or not name_b:
            api.abort(400, 'Both "a" and "b" parameters are required')

        a = _compute_entry(kind, name_a)
        b = _compute_entry(kind, name_b)

        if not a or not b:
            api.abort(404, "One or both entities not found")

        return {
            "kind": kind,
            "a": a,
            "b": b,
        }
