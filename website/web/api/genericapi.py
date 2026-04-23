#!/usr/bin/env python3

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import request
from flask_restx import Namespace, Resource, fields  # type: ignore
from valkey import Valkey

from ransomlook.default import (
    DB_ACTORS,
    DB_GROUPS,
    DB_HEALTH,
    DB_LEAKS,
    DB_MARKETS,
    DB_POSTS,
    DB_RF,
    DB_TASKS,
    get_homedir,
    get_socket_path,
)
from ransomlook.sharedutils import createfile, striptld

api = Namespace("GenericAPI", description="Generic Ransomlook API", path="/api")


def _check_export_auth() -> bool:
    """Check if the request has valid auth for export: admin session, legacy key, or Redis API key."""
    import flask_login  # type: ignore[import-untyped]

    # Admin session
    try:
        if flask_login.current_user.is_authenticated:
            return True
    except Exception:
        pass
    # Legacy API key (generic.json)
    from web.helpers import load_user_from_request  # type: ignore[import-not-found]

    if load_user_from_request(request):
        return True
    # Redis API keys (DB=1)
    token = request.headers.get("Authorization", "").strip()
    if token:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
        raw = red.hget("apikeys", token)
        if raw:
            try:
                meta = json.loads(raw)  # type: ignore[arg-type]
                if meta.get("active", True):
                    meta["last_used"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    red.hset("apikeys", token, json.dumps(meta, ensure_ascii=False))
                    return True
            except Exception:
                pass
    return False


# ── Swagger models ──────────────────────────────────────────────────────

post_model = api.model(
    "Post",
    {
        "post_title": fields.String(description="Title of the post"),
        "discovered": fields.String(description="Discovery timestamp (ISO 8601)"),
        "description": fields.String(description="Post description (may be empty)"),
        "website": fields.String(description="Victim website (if known)"),
        "link": fields.String(description="Original post URL (if available)"),
        "screen": fields.String(description="Base64-encoded screenshot (if available)"),
        "source": fields.String(description="Base64-encoded HTML source (if available)"),
        "group_name": fields.String(description="Name of the group (injected on list endpoints)"),
    },
)

location_model = api.model(
    "Location",
    {
        "slug": fields.String(description="URL / onion address"),
        "available": fields.Boolean(description="Whether the site is currently reachable"),
        "version": fields.Integer(description="Tor hidden service version (2 or 3)"),
        "title": fields.String(description="Page title (last seen)"),
        "screen": fields.String(description="Base64-encoded screenshot (if available)"),
        "source": fields.String(description="Base64-encoded HTML source (if available)"),
    },
)

group_model = api.model(
    "Group",
    {
        "meta": fields.String(description="Description / notes (HTML with <br/> tags)"),
        "locations": fields.List(fields.Nested(location_model), description="Known URLs"),
        "profile": fields.List(fields.String, description="Profile links"),
    },
)

posts_stat_model = api.model(
    "PostStat",
    {
        "group_name": fields.String(description="Group name"),
        "discovered": fields.String(description="ISO 8601 UTC timestamp (Z suffix)"),
    },
)

posts_stat_response = api.model(
    "PostsStatResponse",
    {
        "posts": fields.List(fields.Nested(posts_stat_model)),
    },
)


@api.route("/recent", "/recent/<int:number>")
@api.doc(
    description="Return the X most recent posts across all groups.",
    params={"number": "Number of posts to return (default 100)."},
)
class RecentPost(Resource):  # type: ignore[misc]
    @api.response(200, "List of posts", [post_model])  # type: ignore[untyped-decorator]
    def get(self, number: int = 100) -> list[str]:
        posts = []
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        for key in red.keys():  # type: ignore[union-attr]
            entries = json.loads(red.get(key))  # type: ignore[arg-type]
            for entry in entries:
                entry["group_name"] = key.decode()
                posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)
        recentposts = []
        for post in sorted_posts:
            recentposts.append(post)
            if len(recentposts) == number:
                break
        return recentposts


@api.route("/last", "/last/<int:number>")
@api.doc(
    description="Return posts discovered in the last X days.",
    params={"number": "Number of days to look back (default 1)."},
)
class LastPost(Resource):  # type: ignore[misc]
    @api.response(200, "List of posts", [post_model])  # type: ignore[untyped-decorator]
    def get(self, number: int = 1) -> list[dict[str, Any]]:
        posts = []
        actualdate = datetime.now() + timedelta(days=-number)
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        for key in red.keys():  # type: ignore[union-attr]
            entries = json.loads(red.get(key))  # type: ignore[arg-type]
            for entry in entries:
                try:
                    datetime_object = datetime.strptime(entry["discovered"], "%Y-%m-%d %H:%M:%S.%f")
                except Exception:
                    datetime_object = datetime.strptime(entry["discovered"], "%Y-%m-%d %H:%M:%S")
                if datetime_object > actualdate:
                    entry["group_name"] = key.decode()
                    posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)
        return sorted_posts


@api.route("/groups")
@api.doc(description="Return the list of all public group names.")
class Groups(Resource):  # type: ignore[misc]
    @api.response(200, "List of group names (strings)")  # type: ignore[untyped-decorator]
    def get(self) -> list[str]:
        groups = []
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
        for key in red.keys():  # type: ignore[union-attr]
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if "private" in group and group["private"] is True:
                continue
            groups.append(key.decode())
        return groups


@api.route("/markets")
@api.doc(description="Return the list of all public market / forum names.")
class Markets(Resource):  # type: ignore[misc]
    @api.response(200, "List of market names (strings)")  # type: ignore[untyped-decorator]
    def get(self) -> list[str]:
        groups = []
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
        for key in red.keys():  # type: ignore[union-attr]
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if "private" in group and group["private"] is True:
                continue
            groups.append(key.decode())
        return groups


@api.route("/group/<string:name>")
@api.doc(
    description="Return group metadata, locations and associated posts.",
    params={"name": "Name of the group (case-insensitive)"},
)
class Groupinfo(Resource):  # type: ignore[misc]
    @api.response(200, "Array [group_object, posts_array]")  # type: ignore[untyped-decorator]
    @api.response(404, "Group not found or private (returns [[], {}])")  # type: ignore[untyped-decorator]
    def get(self, name: str) -> list[Any]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
        group = {}
        sorted_posts: list[dict[str, Any]] = []
        for key in red.keys():  # type: ignore[union-attr]
            if key.decode().lower() == name.lower():
                group = json.loads(red.get(key))  # type: ignore[arg-type]
                if "private" in group and group["private"] is True:
                    return [[], {}]

                if group["meta"] is not None:
                    group["meta"] = group["meta"].replace("\n", "<br/>")
                group["locations"] = [
                    location
                    for location in group["locations"]
                    if not ("private" in location and location["private"] is True)
                ]
                for location in group["locations"]:
                    screenfile = "/screenshots/" + name.lower() + "-" + createfile(location["slug"]) + ".png"
                    screenpath = os.path.normpath(str(get_homedir()) + "/source" + screenfile)
                    if not screenpath.startswith(str(get_homedir()) + os.sep):
                        raise Exception("not allowed")
                    if os.path.exists(screenpath):
                        with open(screenpath, "rb") as image_file:
                            screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                        location.update({"screen": screenencoded})
                    source = name.lower() + "-" + striptld(location["slug"]) + ".html"
                    sourcepath = os.path.normpath(str(get_homedir()) + "/source/" + source)
                    if not sourcepath.startswith(str(get_homedir()) + os.sep):
                        raise Exception("not allowed")
                    if os.path.exists(sourcepath):
                        with open(sourcepath, "rb") as text_file:
                            sourceencoded = base64.b64encode(text_file.read()).decode("ascii")
                        location.update({"source": sourceencoded})
                redpost = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
                if key in redpost.keys():  # type: ignore[operator]
                    posts = json.loads(redpost.get(key))  # type: ignore[arg-type]
                    sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)
                else:
                    sorted_posts = []
        return [group, sorted_posts]


@api.route("/post/<string:name>/<string:postname>")
@api.doc(
    description="Return details about a specific post (with screenshot and source if available).",
    params={"name": "Name of the group or market", "postname": "Exact post title"},
)
class GroupPost(Resource):  # type: ignore[misc]
    @api.response(200, "Post object", post_model)  # type: ignore[untyped-decorator]
    @api.response(404, "Post not found (returns {})")  # type: ignore[untyped-decorator]
    def get(self, name: str, postname: str) -> dict[str, Any]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        for key in red.keys():  # type: ignore[union-attr]
            if key.decode().lower() == name.lower():
                posts = json.loads(red.get(key))  # type: ignore[arg-type]
                for post in posts:
                    if post["post_title"] == postname:
                        if "screen" in post and post["screen"] is not None:
                            screenpath = str(get_homedir()) + "/source/" + post["screen"]
                            if os.path.exists(screenpath):
                                with open(screenpath, "rb") as image_file:
                                    screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                                post.update({"screen": screenencoded})
                        if "link" in post and post["link"] is not None:
                            filepath = os.path.normpath(
                                str(get_homedir()) + "/source/" + name + "/" + createfile(postname) + ".html"
                            )
                            if not filepath.startswith(str(get_homedir()) + os.sep):
                                raise Exception("not allowed")
                            if os.path.exists(filepath):
                                with open(filepath, "rb") as src_file:
                                    srcencoded = base64.b64encode(src_file.read()).decode("ascii")
                                post.update({"source": srcencoded})

                        return post
        return {}


@api.route("/market/<string:name>")
@api.doc(
    description="Return market metadata, locations and associated posts.",
    params={"name": "Name of the market (case-insensitive)"},
)
class Marketinfo(Resource):  # type: ignore[misc]
    @api.response(200, "Array [market_object, posts_array]")  # type: ignore[untyped-decorator]
    @api.response(404, "Market not found or private (returns [[], {}])")  # type: ignore[untyped-decorator]
    def get(self, name: str) -> list[Any]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
        group = {}
        sorted_posts: list[dict[str, Any]] = []
        for key in red.keys():  # type: ignore[union-attr]
            if key.decode().lower() == name.lower():
                group = json.loads(red.get(key))  # type: ignore[arg-type]
                if "private" in group and group["private"] is True:
                    return [[], {}]
                if group["meta"] is not None:
                    group["meta"] = group["meta"].replace("\n", "<br/>")
                group["locations"] = [
                    location
                    for location in group["locations"]
                    if not ("private" in location and location["private"] is True)
                ]
                for location in group["locations"]:
                    screenfile = "/screenshots/" + name.lower() + "-" + createfile(location["slug"]) + ".png"
                    screenpath = os.path.normpath(str(get_homedir()) + "/source" + screenfile)
                    if not screenpath.startswith(str(get_homedir()) + os.sep):
                        raise Exception("not allowed")
                    if os.path.exists(screenpath):
                        with open(screenpath, "rb") as image_file:
                            screenencoded = base64.b64encode(image_file.read()).decode("ascii")
                        location.update({"screen": screenencoded})
                    source = name.lower() + "-" + striptld(location["slug"]) + ".html"
                    sourcepath = os.path.normpath(os.path.join(str(get_homedir()) + "/source/", source))
                    if not sourcepath.startswith(str(get_homedir()) + os.sep):
                        raise Exception("not allowed")
                    if os.path.exists(sourcepath):
                        with open(sourcepath, "rb") as text_file:
                            sourceencoded = base64.b64encode(text_file.read()).decode("ascii")
                        location.update({"source": sourceencoded})
                redpost = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
                if key in redpost.keys():  # type: ignore[operator]
                    posts = json.loads(redpost.get(key))  # type: ignore[arg-type]
                    sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)
                else:
                    sorted_posts = []
        return [group, sorted_posts]


_EXPORT_DBS = {
    str(DB_GROUPS): "Groups — ransomware group metadata and locations",
    str(DB_POSTS): "Posts — victim posts across all groups",
    str(DB_MARKETS): "Markets — market / forum metadata and locations",
    str(DB_LEAKS): "Leaks — data breach records",
    str(DB_ACTORS): "Actors — threat actor profiles and relations",
    str(DB_HEALTH): "Health — mirror uptime series (30-day daily)",
    str(DB_RF): "Recorded Future — RF channel data",
}

# DBs where private entries must be filtered out
_EXPORT_FILTER_PRIVATE = {str(DB_GROUPS), str(DB_MARKETS), str(DB_ACTORS)}


@api.route("/export/<database>")
@api.doc(
    description=(
        "Dump a full Redis database for reimport or offline analysis. "
        "Requires a valid API key (Authorization header). "
        "Private entries are filtered from groups (0), markets (3) and actors (5). "
        "Allowed databases: "
        + ", ".join(f"{k} ({v})" for k, v in sorted(_EXPORT_DBS.items(), key=lambda x: int(x[0])))
        + "."
    ),
    params={"database": "Database number: " + ", ".join(sorted(_EXPORT_DBS.keys(), key=int))},
    security="apikey",
)
class Exportdb(Resource):  # type: ignore[misc]
    @api.response(200, "Key-value dump of the database (object)")  # type: ignore[untyped-decorator]
    @api.response(401, "API key required")  # type: ignore[untyped-decorator]
    @api.response(403, "Database not allowed")  # type: ignore[untyped-decorator]
    def get(self, database: int) -> Any:
        if not _check_export_auth():
            api.abort(401, "Valid API key required. Pass it via the Authorization header.")
        if str(database) not in _EXPORT_DBS:
            api.abort(
                403, f"Database {database} is not exportable. Allowed: {', '.join(sorted(_EXPORT_DBS.keys(), key=int))}"
            )
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=database)
        dump = {}
        for key in red.keys():  # type: ignore[union-attr]
            if str(database) in _EXPORT_FILTER_PRIVATE:
                temp = json.loads(red.get(key))  # type: ignore[arg-type]
                if "private" in temp and temp["private"] is True:
                    continue
                if "locations" in temp:
                    temp["locations"] = [
                        location
                        for location in temp["locations"]
                        if not ("private" in location and location["private"] is True)
                    ]
                dump[key.decode()] = temp
            else:
                dump[key.decode()] = json.loads(red.get(key))  # type: ignore[arg-type]
        return dump


# ── Date utilities ───────────────────────────────────────────────────────


def _parse_iso_maybe_z(s: str) -> datetime | None:
    """Parse ISO 8601, accepte ...Z et avec offset. Renvoie un datetime timezone-aware en UTC."""
    if not s:
        return None
    try:
        # remplace 'Z' par +00:00 pour fromisoformat
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # on considère UTC si pas d'info de TZ
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _date_only_to_utc_start(day: str) -> datetime:
    # YYYY-MM-DD -> 00:00:00Z
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)


def _date_only_to_utc_end(day: str) -> datetime:
    # YYYY-MM-DD -> 23:59:59.999999Z
    d = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    return d.replace(hour=23, minute=59, second=59, microsecond=999999)


@api.route("/posts")
@api.doc(
    description="Return posts with group_name and discovered timestamp, filtered by date range. Useful for statistics and charting."
)
class Posts(Resource):  # type: ignore[misc]
    @api.doc(
        params={  # type: ignore[untyped-decorator]
            "days": 'Relative period in days (e.g. 7, 14, 30, 90). Default 30. Ignored if "from" and "to" are provided.',
            "from": "Start date (YYYY-MM-DD) UTC (inclusive). Requires 'to'. If omitted, 'days' is used.",
            "to": "End date (YYYY-MM-DD) UTC (inclusive). Requires 'from'. If omitted, 'days' is used.",
            "groups": "Comma-separated group names to include. Default: all groups.",
        }
    )
    @api.response(200, "Posts matching the filter", posts_stat_response)  # type: ignore[untyped-decorator]
    def get(self) -> dict[str, Any]:
        # --- Time window ---
        now = datetime.now(timezone.utc)
        days = request.args.get("days", type=int)
        from_s = request.args.get("from")
        to_s = request.args.get("to")

        if from_s and to_s:
            try:
                start = _date_only_to_utc_start(from_s)
                end = _date_only_to_utc_end(to_s)
            except Exception:
                # fallback si mauvais format -> dernière 30j
                start = now - timedelta(days=30)
                end = now
        else:
            if not days:
                days = 30
            start = now - timedelta(days=days)
            end = now

        # --- Optional group filter ---
        groups_param = request.args.get("groups", "") or ""
        groups_wanted = set([g.strip() for g in groups_param.split(",") if g.strip()]) if groups_param else None

        # --- Read Redis db=2 as in your script ---
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)

        out: list[dict[str, Any]] = []
        for key in red.keys():  # type: ignore[union-attr]
            group_name = key.decode()
            if groups_wanted and group_name not in groups_wanted:
                continue

            raw = red.get(key)
            if not raw:
                continue

            try:
                posts = json.loads(raw)  # type: ignore[arg-type]
            except Exception:
                continue

            for p in posts:
                ts_s = p.get("discovered")
                dt = _parse_iso_maybe_z(ts_s)
                if not dt:
                    continue
                if start <= dt <= end:
                    out.append(
                        {
                            "group_name": group_name,
                            "discovered": dt.isoformat().replace("+00:00", "Z"),  # propre ISO en Z
                        }
                    )

        # On peut trier par date pour plus de cohérence (optionnel)
        out.sort(key=lambda r: r["discovered"])

        return {"posts": out}


@api.route("/group-first-seen")
@api.doc(description=(
    "Return the earliest discovered timestamp of each tracked group "
    "across the whole post database. Used by the /stats page to tell "
    "truly new groups apart from groups that merely resumed activity."
))
class GroupFirstSeen(Resource):  # type: ignore[misc]
    def get(self) -> dict[str, str]:
        red_posts = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        out: dict[str, str] = {}

        def _parse_ts(s: str) -> Any:
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(s, fmt)
                except Exception:
                    pass
            return None

        for key in red_posts.keys():  # type: ignore[union-attr]
            try:
                entries = json.loads(red_posts.get(key))  # type: ignore[arg-type]
            except Exception:
                continue
            gname = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
            earliest: Any = None
            for entry in entries:
                ts = _parse_ts(entry.get("discovered") or "")
                if ts is None:
                    continue
                if earliest is None or ts < earliest:
                    earliest = ts
            if earliest is not None:
                out[gname] = earliest.strftime("%Y-%m-%dT%H:%M:%SZ")
        return out


@api.route("/posts/<year>/<month>")
@api.route("/posts/<year>")
@api.doc(
    description="Return all posts for a given year, or a specific month (YYYY/MM).",
    params={"year": "Year (e.g. 2025)", "month": "Month 1-12 (optional)"},
)
class PostPerMonth(Resource):  # type: ignore[misc]
    @api.response(200, "List of posts", [post_model])  # type: ignore[untyped-decorator]
    def get(self, year: int, month: int | None = None) -> list[dict[str, Any]]:
        posts = []
        if month is not None:
            date = str(year) + "-" + str(month)
        else:
            date = str(year) + "-"
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        for key in red.keys():  # type: ignore[union-attr]
            entries = json.loads(red.get(key))  # type: ignore[arg-type]
            for entry in entries:
                if entry["discovered"].startswith(date):
                    entry["group_name"] = key.decode()
                    posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)
        return sorted_posts


@api.route("/posts/period/<start_date>/<end_date>")
@api.doc(
    description="Return all posts between two dates (inclusive, YYYY-MM-DD format).",
    params={"start_date": "Start date (YYYY-MM-DD)", "end_date": "End date (YYYY-MM-DD)"},
)
class PostPerPeriod(Resource):  # type: ignore[misc]
    @api.response(200, "List of posts", [post_model])  # type: ignore[untyped-decorator]
    def get(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        posts = []
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        for key in red.keys():  # type: ignore[union-attr]
            entries = json.loads(red.get(key))  # type: ignore[arg-type]
            for entry in entries:
                if start_date <= entry["discovered"].split(" ")[0] <= end_date:
                    entry["group_name"] = key.decode()
                    posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)
        return sorted_posts
