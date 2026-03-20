import ast
import csv
import datetime
import glob
import hashlib
import imghdr
import json
import mimetypes
import os
import random
import re
import time
import unicodedata
from collections import OrderedDict, defaultdict, namedtuple
from datetime import datetime as dt
from datetime import timedelta
from datetime import timezone
from importlib.metadata import version
from io import StringIO
from os import listdir
from os.path import basename, dirname, isfile, join
from typing import Any, Dict, Optional
from urllib.parse import quote
from uuid import uuid4

import flask_login  # type: ignore[import-untyped]
import flask_moment  # type: ignore
from dateutil import parser
from flask import (
    Flask,
    Request,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_bootstrap import Bootstrap5  # type: ignore
from flask_login import current_user
from flask_restx import Api  # type: ignore
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from valkey import Valkey
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from ransomlook.default import (
    DB_ACTORS,
    DB_ALERTS,
    DB_CRYPTO,
    DB_GROUPS,
    DB_HEALTH,
    DB_LACUS,
    DB_LEAKS,
    DB_MARKETS,
    DB_NOTES,
    DB_POSTS,
    DB_RF,
    DB_TASKS,
    get_socket_path,
)
from ransomlook.default.config import get_config, get_homedir
from ransomlook.posts import appender
from ransomlook.ransomlook import adder
from ransomlook.sharedutils import (
    actorcount,
    createfile,
    cryptostats,
    currentmonthstr,
    groupcount,
    hostcount,
    hostcountadmin,
    hostcountchat,
    hostcountdls,
    hostcountfs,
    leakcount,
    mounthlypostcount,
    notecount,
    onlinecount,
    parsercount,
    postcount,
    postslast24h,
    postssince,
    poststhisyear,
    rfcount,
)

from .api.actorsapi import api as actors_api
from .api.cryptoapi import api as crypto_api

# DB constants are imported from ransomlook.default
from .api.genericapi import api as generic_api
from .api.leaksapi import api as leaks_api
from .api.notesapi import api as notes_api
from .api.rfapi import api as rf_api
from .api.statsapi import api as stats_api
from .forms import (
    ActorSelectForm,
    AddActorForm,
    AddForm,
    AddPostForm,
    AlertForm,
    DeleteForm,
    EditActorForm,
    EditForm,
    EditLogo,
    EditPostsForm,
    LoginForm,
    SelectForm,
)
from .helpers import User, build_users_table, get_secret_key, load_user_from_request, sri_load
from .ldap import global_ldap_authentication


def _norm_for_sort(s: str) -> str:
    try:
        return unicodedata.normalize("NFKD", str(s)).casefold()
    except Exception:
        return str(s).lower()


def _norm_group(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "-").replace("_", "-")
    s = re.sub(r"[^a-z0-9\-]+", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


class App(Flask):
    def get_send_file_max_age(self, filename: str) -> int:
        name = str(filename)
        if name.startswith("img/"):  # ne concerne que /static/img/*
            return 31536000  # 1 an
        return super().get_send_file_max_age(filename)


app = App(__name__, static_folder="static", static_url_path="/static")

dbvalue = {DB_GROUPS: "group", DB_MARKETS: "market", DB_ACTORS: "actor"}
ALIAS_PREFIX = "crypto:alias:"

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_for=1)  # type: ignore[method-assign]
app.jinja_env.filters["quote_plus"] = lambda u: quote(u)
app.config["SECRET_KEY"] = get_secret_key()
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["UPLOAD_EXTENSIONS"] = [".png", ".jpg", ".svg", ".gif"]
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
Bootstrap5(app)
app.config["BOOTSTRAP_SERVE_LOCAL"] = True
app.config["SESSION_COOKIE_NAME"] = "RansomLook"
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
if get_config("generic", "darkmode"):
    app.config["BOOTSTRAP_BOOTSWATCH_THEME"] = "slate"
app.debug = False


class CustomRequest(Request):
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.max_form_parts = 200000


app.request_class = CustomRequest

pkg_version = version("ransomlook")

flask_moment.Moment(app=app)


@app.context_processor
def inject_now() -> dict[str, Any]:
    return {"now": dt.utcnow}


@app.context_processor
def _crypto_ctx_processor() -> dict[str, Any]:
    # In templates: {% set crypto = resolve_crypto_for(group) %}
    def resolve_crypto_for(group: dict[str, Any]) -> Any:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
        candidates = [str(group.get("name") or "").strip().lower()]
        for fld in ("aliases", "aka", "alt_names"):
            vals = group.get(fld)
            if isinstance(vals, str):
                vals = [s.strip() for s in vals.split(",") if s.strip()]
            if isinstance(vals, list):
                candidates += [str(v).strip().lower() for v in vals]
        seen = set()
        cand = []
        for x in candidates:
            if x and x not in seen:
                seen.add(x)
                cand.append(x)
        for name in cand:
            raw = red.get(name)
            if raw is not None:
                try:
                    return json.loads(raw)  # type: ignore[arg-type]
                except Exception:
                    return None
            norm = re.sub(r"[^a-z0-9]+", "", name)
            akey = ALIAS_PREFIX + norm
            target = red.get(akey)
            if target is not None:
                t = target.decode()  # type: ignore[union-attr]
                raw = red.get(t)
                if raw is not None:
                    try:
                        return json.loads(raw)  # type: ignore[arg-type]
                    except Exception:
                        return None
        return None

    return dict(resolve_crypto_for=resolve_crypto_for)


def _split_lines(txt: str) -> list[str]:
    if not txt:
        return []
    return [l.strip() for l in txt.replace("\r", "").split("\n") if l.strip()]


def _split_csv(txt: str) -> list[str]:
    if not txt:
        return []
    return [t.strip() for t in txt.split(",") if t.strip()]


def _actor_db() -> Valkey:
    return Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)


def validate_image(stream):  # type: ignore[no-untyped-def]
    allowed_formats = {"jpg", "png", "svg", "gif"}  # Allowed formats
    header = stream.read(512)  # Read the initial bytes of the file
    stream.seek(0)

    # Check for SVG based on its XML header or <svg> tag
    if header.lstrip().startswith(b"<?xml") or b"<svg" in header[:100].lower():
        return ".svg"

    # Check for other formats using imghdr
    format = imghdr.what(None, header)

    if format == "jpeg":  # Treat jpeg as jpg
        format = "jpg"

    # Return the format if it's allowed
    if format in allowed_formats:
        return "." + format

    # If format is not recognized or not allowed
    return None


def _norm_telegram(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return v
    if v.startswith("@"):
        return f"https://t.me/{v[1:]}"
    if v.startswith("t.me/"):
        return f"https://{v}"
    return v


def _norm_x(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return v
    if v.startswith("@"):
        return f"https://x.com/{v[1:]}"
    if "twitter.com/" in v:
        return v.replace("twitter.com", "x.com")
    return v


def _normalize_contacts(c: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, vals in (c or {}).items():
        L = []
        for v in vals or []:
            if not v:
                continue
            if k == "telegram":
                L.append(_norm_telegram(v))
            elif k == "x":
                L.append(_norm_x(v))
            else:
                L.append(v.strip())
        out[k] = L
    return out


# ---------- Normalization & utils ----------
def _norm_key(s: str) -> str:
    return (s or "").strip().lower()


def _lines(text: str) -> list[str]:
    return [l.strip() for l in (text or "").replace("\r", "").split("\n") if l.strip()]


def _join_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def _resolve_key(red: Valkey, key_lower: str) -> Any:
    for kk in red.keys():  # type: ignore[union-attr]
        if kk.decode().lower() == key_lower:
            return kk
    return None


def _load_json(red: Valkey, k: Any) -> Any:
    try:
        raw = red.get(k)
        return json.loads(raw) if raw else None  # type: ignore[arg-type]
    except Exception:
        return None


def _save_json(red: Valkey, k: Any, obj: dict[str, Any]) -> None:
    red.set(k, json.dumps(obj, ensure_ascii=False))


# ---------- Backlinks vers `affiliates` (db=0 et db=3) ----------
def _set_group_affiliate(group_lower: str, actor_name: str, present: bool) -> None:
    """Ajoute/retire `actor_name` comme ligne dans group['affiliates'] (db=0)."""
    red_g = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    rk = _resolve_key(red_g, group_lower)
    if not rk:
        return
    obj = _load_json(red_g, rk) or {}
    existing = _lines(obj.get("affiliates") or "")
    if present:
        if actor_name.lower() not in [x.lower() for x in existing]:
            existing.append(actor_name)
            obj["affiliates"] = _join_lines(existing)
            _save_json(red_g, rk, obj)
    else:
        new = [x for x in existing if x.lower() != actor_name.lower()]
        if len(new) != len(existing):
            obj["affiliates"] = _join_lines(new)
            _save_json(red_g, rk, obj)


def _set_market_affiliate(market_lower: str, actor_name: str, present: bool) -> None:
    """Ajoute/retire `actor_name` comme ligne dans market['affiliates'] (db=3)."""
    red_m = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    rk = _resolve_key(red_m, market_lower)
    if not rk:
        return
    obj = _load_json(red_m, rk) or {}
    existing = _lines(obj.get("affiliates") or "")
    if present:
        if actor_name.lower() not in [x.lower() for x in existing]:
            existing.append(actor_name)
            obj["affiliates"] = _join_lines(existing)
            _save_json(red_m, rk, obj)
    else:
        new = [x for x in existing if x.lower() != actor_name.lower()]
        if len(new) != len(existing):
            obj["affiliates"] = _join_lines(new)
            _save_json(red_m, rk, obj)


# ---------- Réciproque entre acteurs (db=5), inchangée ----------
def _dedup_peers(items: list[Any]) -> list[Any]:
    out, seen = [], set()
    for it in items or []:
        name = (it.get("name") if isinstance(it, dict) else str(it)) or ""
        key = name.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(
                {"name": name, **({k: v for k, v in (it or {}).items() if k != "name"} if isinstance(it, dict) else {})}
            )
    return out


def _set_peer_has_actor(peer_lower: str, actor_name: str, present: bool) -> None:
    red_a = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    rk = _resolve_key(red_a, peer_lower)
    if not rk:
        return
    obj = _load_json(red_a, rk) or {}
    rel = obj.get("relations") or {}
    peers = rel.get("peers") or []

    if present:
        names_ci = [(p.get("name") if isinstance(p, dict) else str(p)).lower() for p in peers]  # type: ignore[union-attr]
        if actor_name.lower() not in names_ci:
            peers.append({"name": actor_name})
            rel["peers"] = _dedup_peers(peers)
            obj["relations"] = rel
            _save_json(red_a, rk, obj)
    else:
        new = [p for p in peers if (p.get("name") if isinstance(p, dict) else str(p)).lower() != actor_name.lower()]  # type: ignore[union-attr]
        if len(new) != len(peers):
            rel["peers"] = _dedup_peers(new)
            obj["relations"] = rel
            _save_json(red_a, rk, obj)


def _update_actor_relation(actor_lower: str, rel_key: str, value: str, present: bool) -> None:
    """
    rel_key: 'groups' OU 'forums'
    value:   nom du group/market tel qu'affiché (on conserve la casse de value)
    present: True -> ajouter ; False -> retirer
    """
    red_a = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    rk = _resolve_key(red_a, actor_lower)
    if not rk:
        return  # l'acteur n'existe pas → on ignore silencieusement
    obj = _load_json(red_a, rk) or {}
    rel = obj.get("relations") or {}
    arr = rel.get(rel_key) or []

    lower_set = [x.lower() for x in arr]
    changed = False
    if present:
        if value.lower() not in lower_set:
            arr.append(value)
            changed = True
    else:
        new_arr = [x for x in arr if x.lower() != value.lower()]
        if len(new_arr) != len(arr):
            arr = new_arr
            changed = True

    if changed:
        rel[rel_key] = arr
        obj["relations"] = rel
        obj["updated_at"] = dt.utcnow().isoformat() + "Z"  # si tu as déjà dt importé
        _save_json(red_a, rk, obj)


####### HELPERS NOTES
def _now_iso() -> str:
    return dt.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def _r11() -> Valkey:
    return Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)


def _load_note(r: Any, nid: str) -> Any:
    b = r.get(f"note:{nid}")
    return json.loads(b) if b else None


def _save_note(r: Any, note: dict[str, Any]) -> None:
    nid = note["id"]
    pipe = r.pipeline()
    pipe.set(f"note:{nid}", json.dumps(note, ensure_ascii=False))
    # indexes
    try:
        ts = int(dt.fromisoformat(note["updated_at"]).timestamp())
    except Exception:
        ts = int(dt.now(timezone.utc).timestamp())
    pipe.zadd("idx:notes:updated", {nid: ts})
    # status / format
    pipe.sadd(f"idx:status:{note.get('status', 'active')}", nid)
    pipe.sadd(f"idx:format:{note.get('format', 'txt')}", nid)
    # sources
    srcs = note.get("sources", [])
    if any(s.get("kind") == "manual" for s in srcs):
        pipe.sadd("idx:source:manual", nid)
    for s in srcs:
        if s.get("kind") == "git":
            pipe.sadd(f"idx:source:git:{s.get('repo', '')}", nid)
    # groups
    for g in note.get("groups", []):
        pipe.sadd(f"idx:group:{g}:notes", nid)
    pipe.execute()


def _remove_note(r: Any, note: dict[str, Any]) -> None:
    nid = note["id"]
    pipe = r.pipeline()
    pipe.delete(f"note:{nid}")
    pipe.zrem("idx:notes:updated", nid)
    pipe.srem(f"idx:status:{note.get('status', 'active')}", nid)
    pipe.srem(f"idx:format:{note.get('format', 'txt')}", nid)
    for s in note.get("sources", []):
        if s.get("kind") == "manual":
            pipe.srem("idx:source:manual", nid)
        elif s.get("kind") == "git":
            pipe.srem(f"idx:source:git:{s.get('repo', '')}", nid)
    for g in note.get("groups", []):
        pipe.srem(f"idx:group:{g}:notes", nid)
    pipe.execute()


@app.context_processor
def inject_global_vars() -> dict[str, bool]:
    darkmode = False
    activatedRF = False
    if get_config("generic", "darkmode"):
        darkmode = True
    if get_config("generic", "rf") != "":
        activatedRF = True
    return {"darkmode": darkmode, "activatedRF": activatedRF}


# Getting the error
# @app.errorhandler(Exception)
def handle_error(e):  # type: ignore[no-untyped-def]
    code = 500
    if isinstance(e, HTTPException):
        return render_template("40x.html", error=e.name, message=e.description), code
    app.logger.error(e)
    return render_template("500_generic.html", e=e), 500


@app.route("/favicon.ico")
def favicon():  # type: ignore[no-untyped-def]
    return send_from_directory(
        os.path.join(get_homedir(), "website/web/static"), "ransomlook.svg", mimetype="image/svg+xml"
    )


ldap_config = get_config("generic", "ldap")
ldap = ldap_config["enable"]
# Auth stuff
login_manager = flask_login.LoginManager()
login_manager.init_app(app)


@login_manager.user_loader  # type: ignore[untyped-decorator]
def user_loader(username: str) -> str | None:
    if not ldap:
        if username not in build_users_table():
            return None
    user = User()
    user.id = username
    return user


@login_manager.request_loader
def _load_user_from_request(request):  # type: ignore
    return load_user_from_request(request)  # type: ignore[no-untyped-call]


@app.route("/login", methods=["GET", "POST"])
def login():  # type: ignore[no-untyped-def]
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        if not ldap_config["enable"]:
            users_table = build_users_table()
            if username in users_table and check_password_hash(users_table[username]["password"], form.password.data):  # type: ignore[no-untyped-call]
                user = User()
                user.id = username
                flask_login.login_user(user)
                audit_log("login", username, "local auth")
                flash(f"Logged in as: {flask_login.current_user.id}", "success")
                return redirect(url_for("admin"))
            else:
                audit_log("login_failed", username, "local auth")
                flash(f"Unable to login as: {username}", "error")
        else:
            if global_ldap_authentication(username, form.password.data, ldap_config):
                user = User()
                user.id = username
                flask_login.login_user(user)
                audit_log("login", username, "LDAP auth")
                flash(f"Logged in as: {flask_login.current_user.id}", "success")
                return redirect(url_for("admin"))
            else:
                audit_log("login_failed", username, "LDAP auth")
                flash(f"Unable to login as: {username}", "error")
    return render_template("login.html", form=form)


@app.route("/logout")
@flask_login.login_required
def logout():  # type: ignore
    username = flask_login.current_user.id if flask_login.current_user.is_authenticated else "?"
    flask_login.logout_user()
    audit_log("logout", username)
    flash("Successfully logged out.", "success")
    return redirect(url_for("home"))


# End auth


def get_sri(directory: str, filename: str) -> str:
    sha512 = sri_load()[directory][filename]
    return f"sha512-{sha512}"


app.jinja_env.globals.update(get_sri=get_sri)


def suffix(d: int) -> str:
    return "th" if 11 <= d <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")


def custom_strftime(fmt, t) -> str:  # type: ignore
    return t.strftime(fmt).replace("{S}", str(t.day) + suffix(t.day))


@app.route("/")
def home():  # type: ignore[no-untyped-def]
    date = custom_strftime("%B {S}, %Y", dt.now()).lower()
    data = {}
    data["nbgroups"] = groupcount(0)
    data["nblocations"] = hostcount(0)
    data["nbdls"] = hostcountdls(0)
    data["nbfs"] = hostcountfs(0)
    data["nbchat"] = hostcountchat(0)
    data["nbadmin"] = hostcountadmin(0)
    data["online"] = onlinecount(0)
    data["nbforum"] = groupcount(3)
    data["nbforumlocations"] = hostcount(3)
    data["forumonline"] = onlinecount(3)
    data["24h"] = postslast24h()
    data["monthlypost"] = mounthlypostcount()
    data["month"] = currentmonthstr()  # type: ignore
    data["90d"] = postssince(90)
    data["yearlypost"] = poststhisyear()
    data["year"] = dt.now().year
    data["nbposts"] = postcount()
    data["nbparsers"] = parsercount()
    data["nbactors"] = actorcount()
    crypto = cryptostats()
    data["nbcryptoaddr"] = crypto["addresses"]
    data["nbcryptotx"] = crypto["transactions"]
    data["nbnotes"] = notecount()
    data["nbleaks"] = leakcount()
    data["nbrf"] = rfcount()
    alertposts = defaultdict(list)
    alert = get_config("generic", "alertondashboard")
    if alert is True:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ALERTS)
        groups = red.keys()
        for entry in groups:  # type: ignore[union-attr]
            post = json.loads(red.get(entry))  # type: ignore[arg-type]
            alertposts[post["type"]].append(post)
    logos = get_config("generic", "logos")
    paths = list(logos.keys())
    weights = list(logos.values())
    logo = random.choices(paths, weights=weights, k=1)[0]

    return render_template("index.html", date=date, data=data, alert=alert, posts=alertposts, logo=logo)


@app.route("/recent")
def recent():  # type: ignore[no-untyped-def]
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
        if len(recentposts) == 100:
            break
    return render_template("recent.html", data=recentposts)


# ---- Hot / Trending (Derniers X jours) ----
@app.route("/hot")
def hot():  # type: ignore[no-untyped-def]
    try:
        number = int(request.args.get("days", "7"))
    except Exception:
        number = 7
    if number < 1:
        number = 1
    if number > 365:
        number = 365

    posts = []
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
    actualdate = dt.now() + timedelta(days=-number)

    for key in red.keys():  # type: ignore[union-attr]
        try:
            entries = json.loads(red.get(key))  # type: ignore[arg-type]
        except Exception:
            continue
        for entry in entries:
            # parse date
            dt_obj = None
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt_obj = dt.strptime(entry.get("discovered", ""), fmt)
                    break
                except Exception:
                    pass
            if not dt_obj:
                continue
            if dt_obj > actualdate:
                e = dict(entry)
                e["group_name"] = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
                posts.append(e)

    by_group = {}
    for p in posts:
        g = p.get("group_name", "").lower()
        if g not in by_group:
            by_group[g] = {"group": g, "count": 0, "last_post": None}
        by_group[g]["count"] += 1
        dp = p.get("discovered")
        if dp:
            by_group[g]["last_post"] = max(by_group[g]["last_post"], dp) if by_group[g]["last_post"] else dp

    rows = sorted(by_group.values(), key=lambda x: (x["count"], x["last_post"] or ""), reverse=True)

    # Total
    total_posts = len(posts)

    return render_template(
        "hot.html",
        days=number,
        rows=rows,
        total_posts=total_posts,
        from_date=actualdate.strftime("%Y-%m-%d"),
    )


@app.route("/rss.xml")
def feeds():  # type: ignore[no-untyped-def]
    posts = []
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)

    # Iterate over Redis keys and parse entries
    for key in red.keys():  # type: ignore[union-attr]
        entries = json.loads(red.get(key))  # type: ignore[arg-type]
        for entry in entries:
            entry["group_name"] = key.decode()
            posts.append(entry)

    # Sort posts by 'discovered' field
    sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)

    recentposts = []
    for post in sorted_posts:
        # Convert 'discovered' to UTC datetime and format as RFC 2822
        if "discovered" in post:
            discovered_time = dt.strptime(post["discovered"].split(".")[0], "%Y-%m-%d %H:%M:%S")
            discovered_utc = discovered_time.replace(tzinfo=timezone.utc)
            post["discovered"] = discovered_utc.strftime("%a, %d %b %Y %T GMT")
        else:
            # Fallback to current UTC time if 'discovered' is missing
            post["discovered"] = dt.now(timezone.utc).strftime("%a, %d %b %Y %T GMT")

        # Generate GUID for the post
        post["guid"] = hashlib.sha256((post["post_title"] + post["group_name"]).encode()).hexdigest()

        recentposts.append(post)

        # Limit the number of recent posts
        if len(recentposts) == 50:
            break

    # Render the RSS feed
    return render_template(
        "rss.xml",
        posts=recentposts,
        build_date=dt.now(timezone.utc).strftime("%a, %d %b %Y %T GMT"),
    ), {"Content-Type": "application/xml"}


@app.route("/stats")
def stats():  # type: ignore[no-untyped-def]
    return render_template("stats.html")


@app.route("/about")
def about():  # type: ignore[no-untyped-def]
    logos = get_config("generic", "logos")
    paths = list(logos.keys())
    weights = list(logos.values())
    logo = random.choices(paths, weights=weights, k=1)[0]
    return render_template("about.html", logo=logo)


@app.route("/groups")
def groups():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)

    groups = []
    for key in red.keys():  # type: ignore[union-attr]
        entry = json.loads(red.get(key))  # type: ignore[arg-type]
        if not current_user.is_authenticated and "private" in entry and entry["private"] is True:
            continue
        entry["name"] = key.decode()
        groups.append(entry)
    groups.sort(key=lambda x: x["name"].lower())
    for group in groups:
        for location in group["locations"]:
            screenfile = "/screenshots/" + group["name"] + "-" + createfile(location["slug"]) + ".png"
            if os.path.exists(str(get_homedir()) + "/source" + screenfile):
                location["screen"] = screenfile
    modules = glob.glob(join(dirname(str(get_homedir()) + "/ransomlook/parsers/"), "*.py"))
    parserlist = [basename(f)[:-3].split(".")[0] for f in modules if isfile(f) and not f.endswith("__init__.py")]
    return render_template("groups.html", data=groups, parser=parserlist, type="groups")


@app.route("/group/<name>")
def group(name: str):  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    for key in red.keys():  # type: ignore[union-attr]
        if key.decode().lower() == name.lower():
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if not current_user.is_authenticated and "private" in group and group["private"] is True:
                return redirect(url_for("home"))
            base_path = os.path.normpath(str(get_homedir()) + "/source/logo/group/")
            logofolder = os.path.normpath(os.path.join(base_path, name))
            logo = []
            if not logofolder.startswith(base_path + os.sep) and logofolder != base_path:
                raise Exception("Invalid path")
            if os.path.exists(logofolder):
                listlogo = [f for f in listdir(logofolder) if isfile(join(logofolder, f))]
                for f in listlogo:
                    logo.append("/logo/group/" + name + "/" + f)

            group["name"] = key.decode()
            if group["meta"] is not None:
                group["meta"] = group["meta"].replace("\n", "<br/>")
            for location in group["locations"]:
                screenfile = "/screenshots/" + group["name"] + "-" + createfile(location["slug"]) + ".png"
                if os.path.exists(str(get_homedir()) + "/source" + screenfile):
                    location["screen"] = screenfile
                # Load mirror health series (if available)
                try:
                    redhealth = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_HEALTH)
                except Exception:
                    redhealth = None
                if redhealth:
                    try:
                        hkey = f"health:{group['name']}:{location['slug']}"
                        hraw = redhealth.get(hkey)
                        if hraw:
                            series = json.loads(hraw)  # type: ignore[arg-type]
                            if isinstance(series, list) and series:
                                series = series[-30:]
                                norm = [1 if (x in (1, True, "1", "up", "active")) else 0 for x in series]
                                location["health"] = norm
                                location["uptime30"] = round(100 * sum(norm) / len(norm))
                    except Exception:
                        pass

            redpost = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
            if key in redpost.keys():  # type: ignore[operator]
                posts = json.loads(redpost.get(key))  # type: ignore[arg-type]
                sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)
            else:
                sorted_posts = []
            modules = glob.glob(join(dirname(str(get_homedir()) + "/ransomlook/parsers/"), "*.py"))
            parserlist = [
                basename(f)[:-3].split(".")[0] for f in modules if isfile(f) and not f.endswith("__init__.py")
            ]
            group["db"] = 0
            # Affiliates known/unknown (actors in db=5, aff_known=aff_known, aff_unknown=aff_unknown)
            reda = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
            aff_lines = [l.strip() for l in (group.get("affiliates") or "").replace("\r", "").split("\n") if l.strip()]
            aff_known, aff_unknown = [], []
            for a in aff_lines:
                # case-insensitive existence
                found = False
                for kk in reda.keys():  # type: ignore[union-attr]
                    if kk.decode().lower() == a.lower():
                        found = True
                        break
                if found:
                    aff_known.append(a)
                else:
                    aff_unknown.append(a)
            # --- Ransom notes (DB=11) ---
            try:
                rednotes = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)
            except Exception:
                rednotes = None

            note_previews = []
            note_count = 0
            if rednotes:
                try:
                    gslug = _norm_group(group["name"] if isinstance(group, dict) else name)

                    canon = gslug
                    mapped = rednotes.hget("alias:group", gslug)
                    if mapped:
                        canon = mapped.decode()  # type: ignore[union-attr]  # hacks with the aliases

                    # Slug + alias éventuels
                    idset_keys = [f"idx:group:{canon}:notes"]
                    try:
                        aliases: Any = rednotes.smembers(f"group:{canon}:aliases") or []
                        for a in aliases:
                            a_slug = a.decode()
                            idset_keys.append(f"idx:group:{a_slug}:notes")
                    except Exception:
                        pass

                    # Collecte d'IDs
                    note_ids = set()
                    for kset in idset_keys:
                        try:
                            for nid in rednotes.smembers(kset):  # type: ignore[union-attr]
                                note_ids.add(nid.decode())
                        except Exception:
                            pass

                    note_count = len(note_ids)

                    # Top 5 par fraîcheur via l'index temporel
                    if note_ids:
                        ids = list(note_ids)
                        pipe = rednotes.pipeline()
                        for i in ids:
                            pipe.zscore("idx:notes:updated", i)
                        scores = pipe.execute()  # type: ignore[no-untyped-call]
                        ids_sorted = [x for _, x in sorted(zip(scores, ids), key=lambda t: t[0] or 0, reverse=True)]

                        pipe = rednotes.pipeline()
                        for i in ids_sorted[:5]:
                            pipe.get(f"note:{i}")
                        raws = pipe.execute()  # type: ignore[no-untyped-call]
                        for b in raws:
                            if not b:
                                continue
                            try:
                                n = json.loads(b)
                                note_previews.append(
                                    {
                                        "id": n.get("id"),
                                        "title": n.get("title"),
                                        "format": n.get("format"),
                                        "updated_at": n.get("updated_at"),
                                    }
                                )
                            except Exception:
                                pass
                except Exception:
                    pass
            red7 = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
            alias_basis = group.get("name") if isinstance(group, dict) and group.get("name") else name
            alias_norm = re.sub(r"[^a-z0-9]+", "", (alias_basis or "").lower())
            _canon_raw = red7.get("crypto:alias:" + alias_norm)
            _canon = _canon_raw.decode() if _canon_raw else (alias_basis or "").strip() or "Unknwn"  # type: ignore[union-attr]
            crypto_link = url_for("cryptodetail", name=_canon)

            return render_template(
                "group.html",
                group=group,
                posts=sorted_posts,
                parser=parserlist,
                logo=logo,
                aff_known=aff_known,
                aff_unknown=aff_unknown,
                note_previews=note_previews,
                note_count=note_count,
                crypto_link=crypto_link,
            )

    return redirect(url_for("home"))


@app.route("/markets")
def markets():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)

    groups = []
    for key in red.keys():  # type: ignore[union-attr]
        entry = json.loads(red.get(key))  # type: ignore[arg-type]
        if not current_user.is_authenticated and "private" in entry and entry["private"] is True:
            continue
        entry["name"] = key.decode()
        groups.append(entry)
    groups.sort(key=lambda x: x["name"].lower())
    for group in groups:
        for location in group["locations"]:
            screenfile = "/screenshots/" + group["name"] + "-" + createfile(location["slug"]) + ".png"
            if os.path.exists(str(get_homedir()) + "/source" + screenfile):
                location["screen"] = screenfile
    modules = glob.glob(join(dirname(str(get_homedir()) + "/ransomlook/parsers/"), "*.py"))
    parserlist = [basename(f)[:-3].split(".")[0] for f in modules if isfile(f) and not f.endswith("__init__.py")]
    return render_template("groups.html", data=groups, parser=parserlist, type="markets")


@app.route("/market/<name>")
def market(name: str):  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    for key in red.keys():  # type: ignore[union-attr]
        if key.decode().lower() == name.lower():
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if not current_user.is_authenticated and "private" in group and group["private"] is True:
                return redirect(url_for("home"))
            base_path = os.path.normpath(str(get_homedir()) + "/source/logo/market/")
            logofolder = os.path.normpath(os.path.join(base_path, name))
            logo = []
            if not logofolder.startswith(base_path + os.sep) and logofolder != base_path:
                raise Exception("Invalid path")
            if os.path.exists(logofolder):
                listlogo = [f for f in listdir(logofolder) if isfile(join(logofolder, f))]
                for f in listlogo:
                    logo.append("/logo/market/" + name + "/" + f)
            group["name"] = key.decode()
            redpost = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
            if key in redpost.keys():  # type: ignore[operator]
                posts = json.loads(redpost.get(key))  # type: ignore[arg-type]
                sorted_posts = sorted(posts, key=lambda x: x["discovered"], reverse=True)
            else:
                sorted_posts = []
            group["db"] = 3
            # Affiliates known/unknown (actors in db=5, aff_known=aff_known, aff_unknown=aff_unknown)
            reda = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
            aff_lines = [l.strip() for l in (group.get("affiliates") or "").replace("\r", "").split("\n") if l.strip()]
            aff_known, aff_unknown = [], []
            for a in aff_lines:
                found = False
                for kk in reda.keys():  # type: ignore[union-attr]
                    if kk.decode().lower() == a.lower():
                        found = True
                        break
                if found:
                    aff_known.append(a)
                else:
                    aff_unknown.append(a)
            red7 = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
            alias_basis = group.get("name") if isinstance(group, dict) and group.get("name") else name
            alias_norm = re.sub(r"[^a-z0-9]+", "", (alias_basis or "").lower())
            _canon_raw = red7.get("crypto:alias:" + alias_norm)
            _canon = _canon_raw.decode() if _canon_raw else (alias_basis or "").strip() or "Unknwn"  # type: ignore[union-attr]
            crypto_link = url_for("cryptodetail", name=_canon)

            return render_template(
                "group.html",
                group=group,
                posts=sorted_posts,
                logo=logo,
                aff_known=aff_known,
                aff_unknown=aff_unknown,
                crypto_link=crypto_link,
            )
    return redirect(url_for("home"))


@app.route("/actors")
def actors():  # type: ignore[no-untyped-def]
    red_ta = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    is_public = not current_user.is_authenticated

    data = []
    for key in red_ta.keys():  # type: ignore[union-attr]
        try:
            entry = json.loads(red_ta.get(key))  # type: ignore[arg-type]
        except Exception:
            continue
        if is_public and entry.get("private"):
            continue

        entry["name"] = entry.get("name") or key.decode()
        entry["aliases"] = entry.get("aliases") or []
        entry["has_wanted"] = any(
            bool(entry.get("wanted", {}).get(k, {}).get("url")) for k in ("fbi", "europol", "interpol")
        )
        data.append(entry)

    data.sort(key=lambda x: x["name"].lower())
    return render_template("actors.html", data=data)


@app.route("/actor/<name>")
def actor_details(name: str):  # type: ignore
    red_ta = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    red_groups = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    red_markets = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)

    target_key = None
    for k in red_ta.keys():  # type: ignore[union-attr]
        if k.decode().lower() == name.lower():
            target_key = k
            break
    if not target_key:
        abort(404)

    try:
        actor = json.loads(red_ta.get(target_key))  # type: ignore[arg-type]
    except Exception:
        abort(404)

    if (not current_user.is_authenticated) and actor.get("private"):
        abort(404)

    actor["name"] = actor.get("name") or target_key.decode()

    def exists_in(db: Any, key_lower: str) -> bool:
        for kk in db.keys():
            if kk.decode().lower() == key_lower:
                return True
        return False

    rel = actor.get("relations") or {}
    rel_groups = [g for g in (rel.get("groups") or []) if exists_in(red_groups, g.lower())]
    rel_forums = [f for f in (rel.get("forums") or []) if exists_in(red_markets, f.lower())]

    rel_groupsunk = [g for g in (rel.get("groups") or []) if not exists_in(red_groups, g.lower())]
    rel_forumsunk = [f for f in (rel.get("forums") or []) if not exists_in(red_markets, f.lower())]

    # Peers connus / inconnus
    peers = rel.get("peers") or []
    peer_names = [(p.get("name") if isinstance(p, dict) else str(p)) for p in peers]
    peers_known = [p for p in peer_names if exists_in(red_ta, (p or "").lower())]
    peers_unknown = [p for p in peer_names if p not in peers_known]

    # Images (vignettes)
    images = []
    try:
        base_path = os.path.join(str(get_homedir()), "source", "logo", "actor", actor["name"])
        if os.path.isdir(base_path):
            for fn in sorted(os.listdir(base_path)):
                ext = os.path.splitext(fn)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
                    images.append(fn)
    except Exception:
        images = []

    return render_template(
        "actor.html",
        actor=actor,
        rel_groups=rel_groups,
        rel_groupsunk=rel_groupsunk,
        rel_forums=rel_forums,
        rel_forumsunk=rel_forumsunk,
        peers_known=peers_known,
        peers_unknown=peers_unknown,
        images=images,
    )


@app.route("/leaks")
def leaks():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)

    leaks = []
    for key in red.keys():  # type: ignore[union-attr]
        entry = json.loads(red.get(key))  # type: ignore[arg-type]
        entry["id"] = key
        leaks.append(entry)
    leaks.sort(key=lambda x: x["name"].lower())
    return render_template("leaks.html", data=leaks)


@app.route("/leak/<name>")
def leak(name: str):  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)

    target_key = None
    for key in red.keys():  # type: ignore[union-attr]
        if key.decode().lower() == name.lower():
            target_key = key
            break

    if not target_key:
        return redirect(url_for("home"))

    raw = red.get(target_key)
    group = json.loads(raw) if raw else {}  # type: ignore[arg-type]

    if "meta" in group and group["meta"] is not None:
        group["meta"] = group["meta"].replace("\n", "<br/>")

    wants_json = (
        request.args.get("format", "").lower() == "json"
        or request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"]
    )

    if wants_json:
        payload = {
            "id": name,
            "name": group.get("name") or name,
            "group": {
                "size": group.get("size"),
                "records": group.get("records"),
                "indexed": group.get("indexed"),
                "columns": group.get("columns"),
            },
        }
        return jsonify(payload)
    return redirect(url_for("home"))


@app.route("/notes")
def notes():  # type: ignore[no-untyped-def]
    r11 = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)

    found = set()
    cursor = 0
    while True:
        cursor, keys = r11.scan(cursor=cursor, match="idx:group:*:notes", count=500)  # type: ignore[misc]
        for k in keys:
            k = k.decode()
            parts = k.split(":")
            if len(parts) >= 4 and r11.scard(k) > 0:  # type: ignore[operator]
                found.add(parts[2])
        if cursor == 0:
            break

    alias_to_canon = {}
    raw = r11.hgetall("alias:group") or {}
    for a, c in raw.items():  # type: ignore[union-attr]
        alias_to_canon[a.decode()] = c.decode()

    canon_to_aliases: dict[str, set[str]] = {}
    for alias, canon in alias_to_canon.items():
        canon_to_aliases.setdefault(canon, set()).add(alias)
    for c in list(found):
        als: Any = r11.smembers(f"group:{c}:aliases") or []
        if als:
            canon_to_aliases.setdefault(c, set()).update(x.decode() for x in als)

    canons = sorted({alias_to_canon.get(s, s) for s in found})

    data = [canons[i : i + 3] for i in range(0, len(canons), 3)]

    aliases_by_canon = {c: sorted(list(als)) for c, als in canon_to_aliases.items()}

    return render_template("notes.html", data=data, aliases_by_canon=aliases_by_canon)


@app.route("/notes/<name>")
def notesdetails(name: str):  # type: ignore[no-untyped-def]
    red11 = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)

    slug = _norm_group(name)

    mapped = red11.hget("alias:group", slug)
    if mapped:
        slug = mapped.decode()  # type: ignore[union-attr]

    idset_keys = [f"idx:group:{slug}:notes"]
    try:
        aliases: Any = red11.smembers(f"group:{slug}:aliases") or []
        for a in aliases:
            a_slug = a.decode()
            idset_keys.append(f"idx:group:{a_slug}:notes")
    except Exception:
        pass

    note_ids = set()
    for k in idset_keys:
        try:
            for nid in red11.smembers(k):  # type: ignore[union-attr]
                note_ids.add(nid.decode())
        except Exception:
            pass

    data = []
    if note_ids:
        pipe = red11.pipeline()
        for nid in note_ids:
            pipe.get(f"note:{nid}")
        raw = pipe.execute()  # type: ignore[no-untyped-call]
        for b in raw:
            if not b:
                continue
            try:
                n = json.loads(b)
                data.append(
                    {
                        "name": n.get("title", ""),
                        "content": n.get("content", ""),
                    }
                )
            except Exception:
                continue

    data.sort(key=lambda x: (x.get("name") or "").lower())

    return render_template("notesdetails.html", data=data, group_name=name)


@app.route("/RF")
def rf():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_RF)
    leaks = []
    for key in red.keys():  # type: ignore[union-attr]
        entry = json.loads(red.get(key))  # type: ignore[arg-type]
        leaks.append(entry)
    leaks.sort(key=lambda x: x["name"].lower())
    return render_template("RF.html", data=leaks)


@app.route("/RF/<name>")
def rfdetails(name: str) -> Any:
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_RF)
    target = None
    for key in red.keys():  # type: ignore[union-attr]
        if key.decode().lower() == name.lower():
            target = json.loads(red.get(key))  # type: ignore[arg-type]
            break

    if target is None:
        abort(404)

    if request.args.get("format") == "json":
        return jsonify(target)

    return redirect(url_for("home"))


@app.route("/crypto")
def crypto():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    found = set()
    cursor = 0
    while True:
        cursor, keys = red.scan(cursor=cursor, match="idx:group:*:crypto", count=500)  # type: ignore[misc]
        for k in keys:
            k_dec = k.decode()
            parts = k_dec.split(":")  # ['idx','group',<canon>,'crypto']
            if len(parts) >= 4 and red.scard(k) > 0:  # type: ignore[operator]
                found.add(parts[2])  # canon
        if cursor == 0:
            break

    alias_to_canon = {}
    cursor = 0
    while True:
        cursor, keys = red.scan(cursor=cursor, match=ALIAS_PREFIX + "*", count=500)  # type: ignore[misc]
        for akey in keys:
            tgt = red.get(akey)
            if not tgt:
                continue
            alias_norm = akey.decode()[len(ALIAS_PREFIX) :]
            alias_to_canon[alias_norm] = tgt.decode()  # type: ignore[union-attr]
        if cursor == 0:
            break

    canon_to_aliases: dict[str, set[str]] = {}
    for alias, canon in alias_to_canon.items():
        canon_to_aliases.setdefault(canon, set()).add(alias)

    canons = sorted(found)

    data = [canons[i : i + 3] for i in range(0, len(canons), 3)]

    aliases_by_canon = {c: sorted(list(als)) for c, als in canon_to_aliases.items()}

    return render_template("crypto.html", data=data, aliases=aliases_by_canon)


@app.route("/crypto/<name>")
def cryptodetail(name):  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    # Resolve group (DB=7): try alias, else keep provided name (spaces preserved)
    alias_norm = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    canon_raw = red.get(ALIAS_PREFIX + alias_norm)
    canon = canon_raw.decode() if canon_raw else (name or "").strip() or "Unknwn"  # type: ignore[union-attr]

    # Aliases pointing to this canon
    aliases = []
    cursor = 0
    while True:
        cursor, keys = red.scan(cursor=cursor, match=ALIAS_PREFIX + "*", count=500)  # type: ignore[misc]
        for k in keys:
            tgt = red.get(k)
            if tgt and tgt.decode() == canon:  # type: ignore[union-attr]
                aliases.append(k.decode()[len(ALIAS_PREFIX) :])
        if cursor == 0:
            break
    aliases.sort()

    # Wallets of the group via index
    members = red.smembers(f"idx:group:{canon}:crypto") or set()
    by_chain: dict[str, Any] = {}
    total = 0
    for it in members:  # type: ignore[union-attr]
        ca = it.decode()
        if ":" not in ca:
            continue
        chain, addr = ca.split(":", 1)
        raw = red.get(f"crypto:addr:{chain}:{addr}")
        if not raw:
            continue
        try:
            doc = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            continue
        doc.setdefault("transactions", [])
        doc.setdefault("source", "unknown")
        doc.setdefault("blockchain", chain)
        doc.setdefault("address", addr)
        # Normalize transaction fields for template
        for tx in doc["transactions"]:
            # Time: convert Unix timestamp to ISO string
            t = tx.get("time")
            if isinstance(t, (int, float)):
                try:
                    tx["time"] = dt.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                except (OSError, ValueError):
                    tx["time"] = str(t)
            elif t is not None:
                tx["time"] = str(t)
            # Amount: ensure it's a float
            a = tx.get("amount")
            if a is not None:
                try:
                    tx["amount"] = float(a)
                except (ValueError, TypeError):
                    tx["amount"] = None
        by_chain.setdefault(chain, []).append(doc)
        total += 1

    for ch, lst in by_chain.items():
        lst.sort(key=lambda x: (x.get("tx_count", 0), x.get("last_tx_time") or 0), reverse=True)
    by_chain = dict(sorted(by_chain.items(), key=lambda kv: kv[0]))

    # Build address index for cross-group link detection
    addr_index: dict[str, dict[str, str]] = {}
    for key in red.scan_iter(match="crypto:addr:*"):
        raw = red.get(key)
        if not raw:
            continue
        try:
            d = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            continue
        a = (d.get("address") or "").lower()
        if a:
            addr_index[a] = {"group": d.get("group", "unknown"), "chain": d.get("blockchain", "unknown")}

    return render_template("cryptodetail.html", group=canon, aliases=aliases, by_chain=by_chain, total=total, addr_index=addr_index)


@app.route("/search", methods=["GET", "POST"])
def search():  # type: ignore[no-untyped-def]
    if request.method == "POST":
        query = request.form.get("search")
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
        groups = []
        for key in red.keys():  # type: ignore[union-attr]
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if not current_user.is_authenticated and "private" in group and group["private"] is True:
                continue

            if (
                query.lower() in key.decode().lower()  # type: ignore[union-attr]
                or group["meta"] is not None
                and query.lower() in group["meta"].lower()  # type: ignore[union-attr]
            ):
                group["name"] = key.decode().lower()
                groups.append(group)
        groups.sort(key=lambda x: x["name"].lower())

        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
        markets = []
        for key in red.keys():  # type: ignore[union-attr]
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if not current_user.is_authenticated and "private" in group and group["private"] is True:
                continue

            if (
                query.lower() in key.decode().lower()  # type: ignore[union-attr]
                or group["meta"] is not None
                and query.lower() in group["meta"].lower()  # type: ignore[union-attr]
            ):
                group["name"] = key.decode().lower()
                markets.append(group)
        markets.sort(key=lambda x: x["name"].lower())

        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_LEAKS)
        leaks = []
        for key in red.keys():  # type: ignore[union-attr]
            group = json.loads(red.get(key))  # type: ignore[arg-type]
            if query.lower() in group["name"]:  # type: ignore[union-attr]
                group["key"] = key.decode().lower()
                leaks.append(group)
        leaks.sort(key=lambda x: x["name"].lower())

        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
        posts = []
        for key in red.keys():  # type: ignore[union-attr]
            entries = json.loads(red.get(key))  # type: ignore[arg-type]
            for entry in entries:
                if (
                    query.lower() in entry["post_title"].lower()  # type: ignore[union-attr]
                    or "description" in entry
                    and entry["description"] is not None
                    and query.lower() in entry["description"].lower()  # type: ignore[union-attr]
                ):
                    entry["group_name"] = key.decode()
                    posts.append(entry)
        posts.sort(key=lambda x: x["group_name"].lower())

        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)
        notes = []
        try:
            ids = [i.decode() for i in red.zrevrange("idx:notes:updated", 0, -1)]  # type: ignore[union-attr]
            ids = ids[:2000]

            pipe = red.pipeline()
            for nid in ids:
                pipe.get(f"note:{nid}")
            raw = pipe.execute()  # type: ignore[no-untyped-call]

            ql = query.lower()  # type: ignore[union-attr]
            for b in raw:
                if not b:
                    continue
                try:
                    n = json.loads(b)
                except Exception:
                    continue
                title = (n.get("title") or "").lower()
                content = (n.get("content") or "").lower()
                if (ql in title) or (ql in content):
                    entry = {
                        "group_name": (n.get("groups") or [""])[0],
                        "name": n.get("title", ""),
                        "content": n.get("content", ""),
                    }
                    notes.append(entry)
        except Exception:
            pass

        notes.sort(key=lambda x: x["group_name"].lower())

        return render_template(
            "search.html", query=query, groups=groups, markets=markets, posts=posts, leaks=leaks, notes=notes
        )
    return redirect(url_for("home"))


def get_mime_type(file_path):  # type: ignore[no-untyped-def]
    # Guess the MIME type based on the file extension
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type if mime_type else "application/octet-stream"  # Fallback MIME type


@app.route("/screenshots/<path:file>")
def screenshots(file: str) -> Any:
    base = os.path.join(str(get_homedir()), "source", "screenshots")
    mime_type = get_mime_type(os.path.join(base, file))  # type: ignore[no-untyped-call]
    resp = send_from_directory(base, file, mimetype=mime_type, max_age=0, conditional=True)
    resp.headers["Cache-Control"] = "public, no-cache"
    return resp


@app.route("/screenshots/<group>/<file>")
def screenshotspost(group: str, file: str):  # type: ignore[no-untyped-def]
    fullpath = os.path.normpath(os.path.join(str(get_homedir()) + "/source/screenshots/", group))
    if not fullpath.startswith(str(get_homedir()) + os.sep):
        raise Exception("not allowed")
    if file.endswith(".txt"):
        return send_from_directory(fullpath, file, as_attachment=True)
    return send_from_directory(fullpath, file, mimetype="image/gif")


@app.route("/logo/<database>/<group>/<file>")
def logofile(database: str, group: str, file: str):  # type: ignore[no-untyped-def]
    base = os.path.join(str(get_homedir()), "source", "logo")
    dirpath = os.path.normpath(os.path.join(base, database, group))
    if not dirpath.startswith(base + os.sep):
        abort(403)

    filename = secure_filename(file)
    fullfile = os.path.join(dirpath, filename)

    mime_type = get_mime_type(fullfile)  # type: ignore[no-untyped-call]

    resp = send_from_directory(
        dirpath,
        filename,
        mimetype=mime_type,
        max_age=31536000,  # 1 an
        conditional=True,
    )
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    resp.headers["X-Content-Type-Options"] = "nosniff"

    try:
        st = os.stat(fullfile)
        resp.set_etag(f"{st.st_mtime_ns:x}-{st.st_size:x}")
    except FileNotFoundError:
        pass

    return resp


@app.route("/glossary")
def glossary():  # type: ignore[no-untyped-def]
    return render_template("glossary.html")


# ─── Audit log helper ───────────────────────────────────────────────
_AUDIT_RETENTION = 365  # days


def audit_log(action: str, target: str, details: str = "") -> None:
    """Write a structured JSON audit entry to Redis DB=1 sorted set 'audit'.

    Timestamps are UTC.  Old entries (>1 year) are pruned on every write.
    """
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
    now = dt.now(timezone.utc)
    ts = now.timestamp()
    user = ""
    try:
        user = flask_login.current_user.id
    except Exception:
        user = "system"
    entry = json.dumps(
        {
            "user": user,
            "action": action,
            "target": target,
            "details": details,
            "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        ensure_ascii=False,
    )
    red.zadd("audit", {entry: ts})
    # prune entries older than retention
    cutoff = (now - timedelta(days=_AUDIT_RETENTION)).timestamp()
    red.zremrangebyscore("audit", "-inf", cutoff)


# ─── API key management (DB=1, hash "apikeys") ────────────────────────


def _get_apikeys_redis() -> Valkey:
    return Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)


def check_api_key() -> str | None:
    """Check Authorization header against API keys in Redis DB=1.
    Returns the key name/comment if valid, None otherwise."""
    token = request.headers.get("Authorization", "").strip()
    if not token:
        return None
    red = _get_apikeys_redis()
    raw = red.hget("apikeys", token)
    if not raw:
        return None
    try:
        meta = json.loads(raw)  # type: ignore[arg-type]
    except Exception:
        return None
    if not meta.get("active", True):
        return None
    # Update last_used
    meta["last_used"] = dt.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    red.hset("apikeys", token, json.dumps(meta, ensure_ascii=False))
    return meta.get("name", "")


def require_api_key(f: Any) -> Any:
    """Decorator: require a valid API key (DB=1) or admin session."""
    from functools import wraps

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        # Allow admin users (logged in via session)
        if current_user.is_authenticated:
            return f(*args, **kwargs)
        # Allow legacy API keys from generic.json
        if load_user_from_request(request):  # type: ignore[no-untyped-call]
            return f(*args, **kwargs)
        # Check Redis API keys
        if check_api_key() is not None:
            return f(*args, **kwargs)
        from flask_restx import abort as restx_abort

        restx_abort(401, "Valid API key required. Pass it via the Authorization header.")

    return decorated


# Admin Zone


@app.route("/admin/")
@app.route("/admin")
@flask_login.login_required
def admin():  # type: ignore[no-untyped-def]
    return render_template("/admin/admin.html")


@app.route("/admin/add", methods=["GET", "POST"])
@flask_login.login_required
def addgroup():  # type: ignore[no-untyped-def]
    score = int(round(dt.now().timestamp()))
    form = AddForm()
    if form.validate_on_submit():
        res = adder(
            form.groupname.data.lower(),
            form.url.data,
            form.category.data,
            form.fs.data,
            form.private.data,
            form.chat.data,
            form.admin.data,
            form.browser.data,
            form.init_script.data,
        )
        if res == 2:
            flash(f"URL already exists for {form.groupname.data}: {form.url.data}", "error")
            return render_template("admin/add.html", form=form)
        elif res == 1:
            flash(f"URL added to existing group {form.groupname.data}: {form.url.data}", "success")
            audit_log("add_url", form.groupname.data, f"url={form.url.data}")
            return redirect(url_for("admin"))
        else:
            flash(f"New group created: {form.groupname.data} with URL {form.url.data}", "success")
            audit_log("add_group", form.groupname.data, f"url={form.url.data}")
            return redirect(url_for("admin"))
    return render_template("admin/add.html", form=form)


@app.route("/admin/edit", methods=["GET", "POST"])
@flask_login.login_required
def edit():  # type: ignore[no-untyped-def]
    formSelect = SelectForm()
    formMarkets = SelectForm()
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    keys = red.keys()
    choices = [("", "Please select your group")]
    keys.sort(key=lambda x: x.lower())  # type: ignore[union-attr]
    for key in keys:  # type: ignore[union-attr]
        choices.append((key.decode(), key.decode()))
    formSelect.group.choices = choices

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    keys = red.keys()
    choices = [("", "Please select your Market")]
    keys.sort(key=lambda x: x.lower())  # type: ignore[union-attr]
    for key in keys:  # type: ignore[union-attr]
        choices.append((key.decode(), key.decode()))
    formMarkets.group.choices = choices

    if formSelect.validate_on_submit():
        return redirect("/admin/edit/" + "0" + "/" + formSelect.group.data)
    if formMarkets.validate_on_submit():
        return redirect("/admin/edit/" + "3" + "/" + formMarkets.group.data)
    return render_template("admin/edit.html", form=formSelect, formMarkets=formMarkets)


@app.route("/admin/edit/<database>/<name>", methods=["GET", "POST"])
@flask_login.login_required  # type: ignore
def editgroup(database: int, name: str):  # type: ignore
    score = dt.now().timestamp()
    deleteButton = DeleteForm()

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=database)
    datagroup = json.loads(red.get(name))  # type: ignore[arg-type]
    old_aff_lines = _rl_lines(datagroup.get("affiliates") or "")
    locations = namedtuple(
        "locations",
        [
            "slug",
            "fqdn",
            "timeout",
            "delay",
            "fs",
            "chat",
            "admin",
            "browser",
            "init_script",
            "private",
            "version",
            "available",
            "title",
            "updated",
            "lastscrape",
            "header",
            "fixedfile",
        ],
    )
    locationlist = []
    for entry in datagroup["locations"]:
        locationlist.append(
            locations(
                entry["slug"],
                entry["fqdn"],
                entry["timeout"] if "timeout" in entry else "",
                entry["delay"] if "delay" in entry else "",
                entry["fs"] if "fs" in entry else False,
                entry["chat"] if "chat" in entry else False,
                entry["admin"] if "admin" in entry else False,
                entry["browser"] if "browser" in entry else "",
                entry["init_script"] if "init_script" in entry else "",
                entry["private"] if "private" in entry else False,
                entry["version"],
                entry["available"],
                entry["title"],
                entry["updated"],
                entry["lastscrape"],
                entry["header"] if "header" in entry else "",
                entry["fixedfile"] if "fixedfile" in entry else False,
            )
        )
    data = {
        "groupname": name,
        "description": datagroup["meta"],
        "ransomware_galaxy_value": datagroup["ransomware_galaxy_value"]
        if "ransomware_galaxy_value" in datagroup
        else "",
        "captcha": datagroup["captcha"] if "captcha" in datagroup else False,
        "profiles": datagroup["profile"],
        "jabber": datagroup["jabber"] if "jabber" in datagroup else "",
        "mail": datagroup["mail"] if "mail" in datagroup else "",
        "pgp": datagroup["pgp"] if "pgp" in datagroup else "",
        "hash": datagroup["hash"] if "hash" in datagroup else "",
        "matrix": datagroup["matrix"] if "matrix" in datagroup else "",
        "session": datagroup["session"] if "session" in datagroup else "",
        "telegram": datagroup["telegram"] if "telegram" in datagroup else "",
        "tox": datagroup["tox"] if "tox" in datagroup else "",
        "simplex": datagroup["simplex"] if "simplex" in datagroup else "",
        "max": datagroup["max"] if "max" in datagroup else "",
        "sonar": datagroup["sonar"] if "sonar" in datagroup else "",
        "affiliates": datagroup["affiliates"] if "affiliates" in datagroup else "",
        "other": datagroup["other"] if "other" in datagroup else "",
        "private": datagroup["private"] if "private" in datagroup else False,
        "raas": datagroup["raas"] if "raas" in datagroup else False,
        "links": locationlist,
    }

    form = EditForm(data=data, files=request.files)
    form.groupname.label = name

    if deleteButton.validate_on_submit():
        red.delete(name)
        audit_log("delete_group", name)
        flash(f"Success to delete : {name}", "success")
        return redirect(url_for("admin"))
    if form.validate_on_submit():
        data = json.loads(red.get(name))  # type: ignore[arg-type]
        # snapshot tracked fields before modification
        _old = {
            "meta": data.get("meta", ""),
            "private": data.get("private", False),
            "raas": data.get("raas", False),
            "captcha": data.get("captcha", False),
            "jabber": data.get("jabber", ""),
            "mail": data.get("mail", ""),
            "pgp": data.get("pgp", ""),
            "telegram": data.get("telegram", ""),
            "tox": data.get("tox", ""),
            "matrix": data.get("matrix", ""),
            "affiliates": data.get("affiliates", ""),
            "locations_count": len(data.get("locations", [])),
        }
        data["meta"] = form.description.data
        data["captcha"] = form.captcha.data
        data["ransomware_galaxy_value"] = form.galaxy.data
        data["profile"] = ast.literal_eval(form.profiles.data)
        data["jabber"] = form.jabber.data.strip()
        data["mail"] = form.mail.data.strip()
        data["pgp"] = form.pgp.data.strip()
        data["hash"] = form.hash.data.strip()
        data["matrix"] = form.matrix.data.strip()
        data["session"] = form.session.data.strip()
        data["telegram"] = form.telegram.data.strip()
        data["tox"] = form.tox.data.strip()
        data["simplex"] = form.simplex.data.strip()
        data["max"] = form.max.data.strip()
        data["sonar"] = form.sonar.data.strip()
        data["affiliates"] = form.affiliates.data.strip()
        data["other"] = form.other.data.strip()
        data["private"] = form.private.data
        data["captcha"] = form.captcha.data
        data["raas"] = form.raas.data
        old_slugs = {loc.get("slug", "") for loc in data.get("locations", [])}
        newlocations = []
        deleted_urls = []
        for entry in form.links:
            if entry.delete.data is True:
                deleted_urls.append(entry.slug.data)
                continue
            location = {
                "slug": entry.slug.data,
                "fqdn": entry.fqdn.data,
                "timeout": entry.timeout.data,
                "delay": entry.delay.data,
                "fs": entry.fs.data,
                "chat": entry.chat.data,
                "admin": entry.admin.data,
                "browser": entry.browser.data,
                "init_script": entry.init_script.data,
                "private": entry.private.data,
                "version": entry.version.data,
                "available": entry.available.data,
                "title": entry.title.data,
                "updated": entry.updated.data,
                "lastscrape": entry.lastscrape.data,
                "header": entry.header.data,
                "fixedfile": entry.fixedfile.data,
            }
            newlocations.append(location)
            if entry.file.data is not None:
                filename = entry.file.data.filename
                file_ext = os.path.splitext(filename)[1]
                if file_ext not in app.config["UPLOAD_EXTENSIONS"] or file_ext != validate_image(entry.file.data):  # type: ignore
                    flash(f"Error to add post to : {name} - Screen should be a PNG", "error")
                    return render_template("editentry.html", form=form, deleteform=deleteButton)
                filename = name + "-" + createfile(entry.slug.data) + ".png"
                namefile = os.path.join(get_homedir(), "source/screenshots", filename)
                entry.file.data.save(namefile)
                targetImage = Image.open(namefile)
                metadata = PngInfo()
                metadata.add_text("Source", "RansomLook.io")
                targetImage.save(namefile, pnginfo=metadata)

        data["locations"] = newlocations
        red.set(name, json.dumps(data))

        # --- Backlinks to ACTORS (db=5) from group/market edit ---
        rel_key = "groups" if int(database) == 0 else "forums"
        display_name = (form.groupname.data or name).strip() or name

        new_aff_lines = _rl_lines(data.get("affiliates") or "")
        old_set = {_rl_norm_key(x) for x in old_aff_lines}
        new_set = {_rl_norm_key(x) for x in new_aff_lines}

        added = new_set - old_set
        removed = old_set - new_set

        for a in added:
            _rl_update_actor_relation(a, rel_key, display_name, True)
        for a in removed:
            _rl_update_actor_relation(a, rel_key, display_name, False)
        _new = {
            "meta": data.get("meta", ""),
            "private": data.get("private", False),
            "raas": data.get("raas", False),
            "captcha": data.get("captcha", False),
            "jabber": data.get("jabber", ""),
            "mail": data.get("mail", ""),
            "pgp": data.get("pgp", ""),
            "telegram": data.get("telegram", ""),
            "tox": data.get("tox", ""),
            "matrix": data.get("matrix", ""),
            "affiliates": data.get("affiliates", ""),
            "locations_count": len(data.get("locations", [])),
        }
        changes = [k for k in _old if _old[k] != _new.get(k)]
        # Log deleted URLs explicitly
        for url in deleted_urls:
            audit_log("delete_url", name, f"url={url}")
        # Log added URLs
        new_slugs = {loc.get("slug", "") for loc in newlocations}
        for url in new_slugs - old_slugs:
            if url:
                audit_log("add_url", name, f"url={url}")
        # Log other changes
        field_changes = [k for k in changes if k != "locations_count"]
        if field_changes:
            details = []
            for k in field_changes:
                details.append(f"{k}: {_old[k]!r} -> {_new.get(k)!r}")
            audit_log("modify_group", name, "; ".join(details))
        elif not deleted_urls and not (new_slugs - old_slugs):
            audit_log("modify_group", name, "no changes")
        if name != form.groupname.data:
            red.rename(name, form.groupname.data.lower())

            _rl_rename_in_all_actors(rel_key, name, form.groupname.data.strip())
            audit_log("rename_group", name, f"new_name={form.groupname.data}")
        flash(f"Success to edit : {form.groupname.data}", "success")
        return redirect(url_for("admin"))

    return render_template("admin/editentry.html", form=form, deleteform=deleteButton)


@app.route("/admin/logo", methods=["GET", "POST"])
@flask_login.login_required
def logo():  # type: ignore[no-untyped-def]
    form = SelectForm()
    formMarkets = SelectForm()
    formActors = SelectForm()

    # groups (db=0)
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    g = sorted([k.decode() for k in red.keys()], key=lambda s: s.lower())  # type: ignore[union-attr]
    form.group.choices = [("", "Please select your group")] + [(x, x) for x in g]

    # markets (db=3)
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    m = sorted([k.decode() for k in red.keys()], key=lambda s: s.lower())  # type: ignore[union-attr]
    formMarkets.group.choices = [("", "Please select your market")] + [(x, x) for x in m]

    # actors (db=5)
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    a = sorted([k.decode() for k in red.keys()], key=lambda s: s.lower())  # type: ignore[union-attr]
    formActors.group.choices = [("", "Please select your actor")] + [(x, x) for x in a]

    if form.validate_on_submit():
        return redirect("/admin/logo/0/" + form.group.data)
    if formMarkets.validate_on_submit():
        return redirect("/admin/logo/3/" + formMarkets.group.data)
    if formActors.validate_on_submit():
        return redirect("/admin/logo/5/" + formActors.group.data)

    return render_template("admin/logo.html", form=form, formMarkets=formMarkets, formActors=formActors)


@app.route("/admin/logo/<database>/<name>", methods=["GET", "POST"])
@flask_login.login_required  # type: ignore
def editlogo(database: int, name: str):  # type: ignore
    if not (int(database) == 3 or int(database) == 0 or int(database) == 5):
        return render_template("admin.html")
    logo = namedtuple("logo", ["link"])
    logos = []
    base_path = os.path.normpath(str(get_homedir()) + "/source/logo/" + dbvalue[int(database)])
    logofolder = os.path.normpath(os.path.join(base_path, name))
    if not logofolder.startswith(base_path + os.sep) and logofolder != base_path:
        raise Exception("Invalid path")
    if os.path.exists(logofolder):
        listlogo = [f for f in listdir(logofolder) if isfile(join(logofolder, f))]
        for f in listlogo:
            logos.append(logo("/logo/" + dbvalue[int(database)] + "/" + name + "/" + f))
    data = {"logos": logos}
    form = EditLogo(data=data, files=request.files)
    if form.validate_on_submit():
        for currentlogo in form.logos:
            if currentlogo.delete.data is True:
                os.remove(logofolder + "/" + currentlogo.link.data)
                audit_log("delete_logo", name, f"file={currentlogo.link.data}")
        if form.file.data is not None:
            filename = form.file.data.filename
            file_ext = os.path.splitext(filename)[1]
            if file_ext not in app.config["UPLOAD_EXTENSIONS"] or file_ext != validate_image(form.file.data):  # type: ignore
                flash(f"Error to add post to : {name} - Screen should be a PNG", "error")
                return render_template("admin/editlogo.html", form=form)
            filename = createfile(os.path.splitext(filename)[0]) + file_ext
            if not os.path.exists(logofolder):
                os.mkdir(logofolder)
            logoname = os.path.normpath(logofolder + "/" + filename)
            form.file.data.save(logoname)
            audit_log("upload_logo", name, f"file={filename}")
            return redirect("/admin")
    return render_template("admin/editlogo.html", form=form)


@app.route("/admin/addpost", methods=["GET", "POST"])
@flask_login.login_required
def addpost():  # type: ignore[no-untyped-def]
    formSelect = SelectForm()
    formMarkets = SelectForm()
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    keys = red.keys()
    choices = [("", "Please select your group")]
    keys.sort(key=lambda x: x.lower())  # type: ignore[union-attr]
    for key in keys:  # type: ignore[union-attr]
        choices.append((key.decode(), key.decode()))
    formSelect.group.choices = choices

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    keys = red.keys()
    choices = [("", "Please select your Market")]
    keys.sort(key=lambda x: x.lower())  # type: ignore[union-attr]
    for key in keys:  # type: ignore[union-attr]
        choices.append((key.decode(), key.decode()))
    formMarkets.group.choices = choices

    if formSelect.validate_on_submit():
        return redirect("/admin/addpost/" + "0" + "/" + formSelect.group.data)
    if formMarkets.validate_on_submit():
        return redirect("/admin/addpost/" + "3" + "/" + formMarkets.group.data)
    return render_template("admin/addpost.html", form=formSelect, formMarkets=formMarkets)


@app.route("/admin/addpost/<database>/<name>", methods=["GET", "POST"])
@flask_login.login_required  # type: ignore
def addpostentry(database: int, name: str):  # type: ignore
    form = AddPostForm()

    if form.validate_on_submit():
        entry: dict[str, str | None] = {}
        entry["slug"] = None
        entry["title"] = form.title.data
        if form.description.data:
            entry["description"] = form.description.data
        else:
            entry["description"] = ""
        if form.link.data:
            entry["link"] = form.link.data
        if form.magnet.data:
            entry["magnet"] = form.magnet.data
        if form.link.data and form.magnet.data:
            flash(f"Error to add post to : {name} - You should select Magnet or Link not both", "error")
            return render_template("admin/addpostentry.html", form=form)
        if form.date.data:
            entry["date"] = str(parser.parse(form.date.data))
        uploaded_file = request.files["file"]
        filename = secure_filename(uploaded_file.filename)
        if filename != "":
            file_ext = os.path.splitext(filename)[1]
            if file_ext not in app.config["UPLOAD_EXTENSIONS"] or file_ext != validate_image(uploaded_file.stream):  # type: ignore
                flash(f"Error to add post to : {name} - Screen should be a PNG", "error")
                return render_template("admin/addpostentry.html", form=form)
            filenamepng = createfile(form.title.data) + file_ext
            base_path = os.path.normpath(str(get_homedir()) + "/source/screenshots")
            path = os.path.normpath(os.path.join(base_path, name))
            if not path.startswith(base_path + os.sep) and path != base_path:
                raise Exception("Invalid path")
            if not os.path.exists(path):
                os.mkdir(path)
            namepng = os.path.normpath(os.path.join(path, filenamepng))
            uploaded_file.save(namepng)
            entry["screen"] = str(os.path.join("screenshots", name, filenamepng))
        if appender(entry, name):
            flash(f"Error to add post to : {name} - The entry already exists", "error")
            return render_template("admin/addpostentry.html", form=form)
        else:
            # statsgroup(name.encode())
            # run_data_viz(7)
            # run_data_viz(14)
            # run_data_viz(30)
            # run_data_viz(90)
            audit_log("add_post", name, f"title={form.title.data}")
            flash(f"Success to add post to : {name}", "success")
        return redirect(url_for("admin"))

    form.groupname.label = name
    return render_template("admin/addpostentry.html", form=form)


@app.route("/admin/editpost", methods=["GET", "POST"])
@flask_login.login_required
def editpost():  # type: ignore[no-untyped-def]
    formSelect = SelectForm()
    formMarkets = SelectForm()
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    keys = red.keys()
    choices = [("", "Please select your group")]
    keys.sort(key=lambda x: x.lower())  # type: ignore[union-attr]
    for key in keys:  # type: ignore[union-attr]
        choices.append((key.decode(), key.decode()))
    formSelect.group.choices = choices

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    keys = red.keys()
    choices = [("", "Please select your Market")]
    keys.sort(key=lambda x: x.lower())  # type: ignore[union-attr]
    for key in keys:  # type: ignore[union-attr]
        choices.append((key.decode(), key.decode()))
    formMarkets.group.choices = choices

    if formSelect.validate_on_submit():
        return redirect("/admin/editpost/" + formSelect.group.data)
    if formMarkets.validate_on_submit():
        return redirect("/admin/editpost/" + formMarkets.group.data)
    return render_template("admin/edit.html", form=formSelect, formMarkets=formMarkets)


@app.route("/admin/editpost/<name>", methods=["GET", "POST"])
@flask_login.login_required  # type: ignore
def editpostentry(name: str):  # type: ignore
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
    try:
        posts = json.loads(red.get(name))  # type: ignore[arg-type]
    except Exception:
        return redirect("/admin/editpost")
    postdata = namedtuple("posts", ["post_title", "discovered", "description", "link", "magnet", "screen"])  # type: ignore
    postlist = []
    for entry in posts:
        postlist.append(
            postdata(
                entry["post_title"],
                entry["discovered"],
                entry["description"] if "description" in entry else "",
                entry["link"] if "link" in entry else "",
                entry["magnet"] if "magnet" in entry else "",
                entry["screen"] if "screen" in entry else "",
            )
        )
    _old_titles = {e["post_title"] for e in posts}
    data = {"postslist": postlist}
    form = EditPostsForm(data=data, files=request.files)
    if form.validate_on_submit():
        posts = []
        for field in form.postslist:
            if field.delete.data is True:
                continue
            post = {
                "post_title": field.post_title.data.strip(),
                "discovered": field.discovered.data.strip(),
                "description": field.description.data.strip() if field.description else "",
                "link": field.link.data.strip() if field.link.data else "",
                "magnet": field.magnet.data.strip() if field.magnet.data else "",
            }
            if field.file.data is not None:
                filename = field.file.data.filename
                file_ext = os.path.splitext(filename)[1]
                if file_ext not in app.config["UPLOAD_EXTENSIONS"] or file_ext != validate_image(field.file.data):  # type: ignore
                    flash(f"Error to add post to : {name} - Screen should be a PNG", "error")
                    return render_template("admin/editpost.html", form=form)
                filenamepng = createfile(post["post_title"]) + file_ext
                base_path = os.path.normpath(str(get_homedir()) + "/source/screenshots")
                path = os.path.normpath(os.path.join(base_path, name))
                if not path.startswith(base_path + os.sep) and path != base_path:
                    flash(f"Invalid path: {name}", "error")
                    return render_template("admin/editpost.html", form=form)
                if not os.path.exists(path):
                    os.mkdir(path)
                namepng = os.path.normpath(path + "/" + filenamepng)
                field.file.data.save(namepng)
                post["screen"] = str(os.path.join("screenshots", name, filenamepng))
            else:
                if field.screen.data:
                    post["screen"] = field.screen.data.strip() if field.screen.data else ""
            posts.append(post)
        red.set(name, json.dumps(posts))
        _new_titles = {p["post_title"] for p in posts}
        _added = sorted(_new_titles - _old_titles)
        _removed = sorted(_old_titles - _new_titles)
        parts = []
        if _added:
            parts.append(f"added={', '.join(_added)}")
        if _removed:
            parts.append(f"deleted={', '.join(_removed)}")
        if not parts:
            parts.append("modified")
        audit_log("edit_posts", name, "; ".join(parts))
        flash(f"Success to add post to : {name}", "success")
        return redirect(url_for("admin"))

    return render_template("admin/editpost.html", form=form)


@app.route("/export/<database>")
def exportdb(database: int):  # type: ignore[no-untyped-def]
    if str(database) not in ["0", "2", "3", "4", "5", "6", "7"]:
        flash("You are not allowed to dump this DataBase", "error")
        return redirect(url_for("home"))
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=database)
    dump = {}
    for key in red.keys():  # type: ignore[union-attr]
        if str(database) != "0" and str(database) != "3":
            dump[key.decode()] = json.loads(red.get(key))  # type: ignore[arg-type]
        else:
            temp = json.loads(red.get(key))  # type: ignore[arg-type]
            if not current_user.is_authenticated and "private" in temp and temp["private"] is True:
                continue

            if "locations" in temp:
                for location in temp["locations"]:
                    if "private" in location and location["private"] is True:
                        temp["locations"].remove(location)
            dump[key.decode()] = temp
    return dump


@app.route("/admin/addactor", methods=["GET", "POST"])
@flask_login.login_required
def addactor():  # type: ignore[no-untyped-def]
    form = AddActorForm()
    red_g = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    groups_all = sorted([k.decode() for k in red_g.keys()], key=str.lower)  # type: ignore[union-attr]

    red_m = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    markets_all = sorted([k.decode() for k in red_m.keys()], key=str.lower)  # type: ignore[union-attr]

    red_a = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    peers_all = sorted([k.decode() for k in red_a.keys()], key=str.lower)  # type: ignore[union-attr]

    if form.validate_on_submit():
        key = (form.name.data or "").strip().lower()
        if not key:
            flash("Name required", "error")
            return render_template(
                "admin/addactor.html", form=form, groups_all=groups_all, markets_all=markets_all, peers_all=peers_all
            )

        red = _actor_db()
        if red.get(key):
            flash("This actor already exists.", "error")
            return render_template(
                "admin/addactor.html", form=form, groups_all=groups_all, markets_all=markets_all, peers_all=peers_all
            )

        entry = {
            "db": 5,
            "name": form.name.data.strip(),
            "aliases": _split_csv(form.aliases.data),
            "bio": form.bio.data or "",
            "identity": {
                "first_name": form.first_name.data or "",
                "last_name": form.last_name.data or "",
                "age": form.age.data if form.age.data is not None else None,
                "dob": form.dob.data or "",
                "nationality": form.nationality.data or "",
                "location": form.location.data or "",
                "notes": form.id_notes.data or "",
            },
            "wanted": {
                "fbi": {"url": form.fbi_url.data or "", "id": ""},
                "europol": {"url": form.europol_url.data or "", "id": ""},
                "interpol": {"url": form.interpol_url.data or "", "id": ""},
            },
            "sources": [{"url": u} for u in _split_lines(form.sources.data)],
            "contacts": {
                "jabber": _split_lines(form.jabber.data),
                "email": _split_lines(form.email.data),
                "pgp": _split_lines(form.pgp.data),
                "matrix": _split_lines(form.matrix.data),
                "session": _split_lines(form.session.data),
                "telegram": _split_lines(form.telegram.data),
                "tox": _split_lines(form.tox.data),
                "simplex": _split_lines(form.simplex.data),
                "max": _split_lines(form.max.data),
                "sonar": _split_lines(form.sonar.data),
                "x": _split_lines(form.x.data),
                "bluesky": _split_lines(form.bluesky.data),
            },
            "relations": {
                "groups": _split_csv(form.groups.data),
                "forums": _split_csv(form.forums.data),
                "peers": [{"name": p} for p in _split_csv(form.peers.data)],
            },
            "tags": _split_csv(form.tags.data),
            "private": bool(form.private.data),
            "noactive": bool(form.noactive.data),
            "created_at": dt.utcnow().isoformat() + "Z",
            "updated_at": dt.utcnow().isoformat() + "Z",
        }
        entry["contacts"] = _normalize_contacts(entry["contacts"])
        red.set(key, json.dumps(entry, ensure_ascii=False))
        # --- Backlinks (add) ---

        actor_name = entry["name"]

        new_groups = {_norm_key(g) for g in (entry.get("relations", {}).get("groups") or [])}
        new_forums = {_norm_key(f) for f in (entry.get("relations", {}).get("forums") or [])}
        new_peers = {
            _norm_key(p.get("name") if isinstance(p, dict) else p)  # type: ignore[arg-type]
            for p in (entry.get("relations", {}).get("peers") or [])
        }

        for g in new_groups:
            _set_group_affiliate(g, actor_name, True)
        for f in new_forums:
            _set_market_affiliate(f, actor_name, True)
        for p in [x for x in new_peers if x and x != _norm_key(actor_name)]:
            _set_peer_has_actor(p, actor_name, True)

        base_path = os.path.join(str(get_homedir()), "source", "logo", "actor", entry["name"])
        os.makedirs(base_path, exist_ok=True)

        file = request.files.get("file") if hasattr(form, "file") else None
        if file and file.filename:
            filename = file.filename
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext not in app.config["UPLOAD_EXTENSIONS"] or file_ext != validate_image(file.stream):  # type: ignore
                flash("Image invalide (png/jpg/svg/gif)", "error")
                return render_template("admin/addactor.html", form=form)
            safe = secure_filename(os.path.splitext(filename)[0]) + f"-{int(time.time())}{file_ext}"
            file.stream.seek(0)
            file.save(os.path.join(base_path, safe))

        _actor_details = []
        if entry.get("aliases"):
            _actor_details.append(f"aliases={entry['aliases']}")
        if new_groups:
            _actor_details.append(f"groups={', '.join(sorted(new_groups))}")
        if new_forums:
            _actor_details.append(f"forums={', '.join(sorted(new_forums))}")
        if new_peers:
            _actor_details.append(f"peers={', '.join(sorted(new_peers))}")
        audit_log("add_actor", entry["name"], "; ".join(_actor_details) if _actor_details else "minimal profile")
        flash("Actor created.", "success")
        return redirect(f"/admin/editactor/{quote(entry['name'])}")

    return render_template(
        "admin/addactor.html", form=form, groups_all=groups_all, markets_all=markets_all, peers_all=peers_all
    )


@app.route("/admin/editactor", methods=["GET", "POST"])
@flask_login.login_required
def editactor_select():  # type: ignore[no-untyped-def]
    form = ActorSelectForm()
    red = _actor_db()
    keys = sorted([k.decode() for k in red.keys()], key=lambda s: s.lower())  # type: ignore[union-attr]
    choices = [("", "Please select the actor")] + [(k, k) for k in keys]
    form.actor.choices = choices
    if form.validate_on_submit():
        return redirect(url_for("editactor", name=form.actor.data))
    return render_template("admin/editactor_select.html", form=form)


@app.route("/admin/editactor/<name>", methods=["GET", "POST"])
@flask_login.login_required  # type: ignore[untyped-decorator]
def editactor(name: str):  # type: ignore[no-untyped-def]
    red = _actor_db()
    key = None
    for k in red.keys():  # type: ignore[union-attr]
        if k.decode().lower() == name.lower():
            key = k
            break
    if not key:
        flash("Actor not found", "error")
        return redirect("/admin/editactor")
    red_g = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    groups_all = sorted([k.decode() for k in red_g.keys()], key=str.lower)  # type: ignore[union-attr]
    red_m = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    markets_all = sorted([k.decode() for k in red_m.keys()], key=str.lower)  # type: ignore[union-attr]
    red_a = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    peers_all = sorted([k.decode() for k in red_a.keys()], key=str.lower)  # type: ignore[union-attr]

    actor = json.loads(red.get(key))  # type: ignore[arg-type]

    form = EditActorForm(
        name=actor.get("name", ""),
        aliases=", ".join(actor.get("aliases") or []),
        bio=actor.get("bio", ""),
        private=bool(actor.get("private")),
        noactive=bool(actor.get("noactive")),
        tags=", ".join(actor.get("tags") or []),
        first_name=((actor.get("identity") or {}).get("first_name") or ""),
        last_name=((actor.get("identity") or {}).get("last_name") or ""),
        age=((actor.get("identity") or {}).get("age") or None),
        dob=((actor.get("identity") or {}).get("dob") or ""),
        nationality=((actor.get("identity") or {}).get("nationality") or ""),
        location=((actor.get("identity") or {}).get("location") or ""),
        id_notes=((actor.get("identity") or {}).get("notes") or ""),
        fbi_url=((actor.get("wanted") or {}).get("fbi", {}).get("url") or ""),
        europol_url=((actor.get("wanted") or {}).get("europol", {}).get("url") or ""),
        interpol_url=((actor.get("wanted") or {}).get("interpol", {}).get("url") or ""),
        jabber="\n".join((actor.get("contacts") or {}).get("jabber") or []),
        email="\n".join((actor.get("contacts") or {}).get("email") or []),
        pgp="\n".join((actor.get("contacts") or {}).get("pgp") or []),
        matrix="\n".join((actor.get("contacts") or {}).get("matrix") or []),
        session="\n".join((actor.get("contacts") or {}).get("session") or []),
        telegram="\n".join((actor.get("contacts") or {}).get("telegram") or []),
        tox="\n".join((actor.get("contacts") or {}).get("tox") or []),
        simplex="\n".join((actor.get("contacts") or {}).get("simplex") or []),
        max="\n".join((actor.get("contacts") or {}).get("max") or []),
        sonar="\n".join((actor.get("contacts") or {}).get("sonar") or []),
        x="\n".join((actor.get("contacts") or {}).get("x") or []),
        bluesky="\n".join((actor.get("contacts") or {}).get("bluesky") or []),
        groups=", ".join((actor.get("relations") or {}).get("groups") or []),
        forums=", ".join((actor.get("relations") or {}).get("forums") or []),
        peers=", ".join([p.get("name") for p in ((actor.get("relations") or {}).get("peers") or [])]),
        sources="\n".join(
            [
                s.get("title") + " — " + s.get("url") if s.get("title") else s.get("url")
                for s in (actor.get("sources") or [])
                if s.get("url")
            ]
        ),
    )

    if form.validate_on_submit():
        # snapshot before modification
        _old_actor = {
            "aliases": sorted(actor.get("aliases") or []),
            "bio": actor.get("bio", ""),
            "private": bool(actor.get("private")),
            "noactive": bool(actor.get("noactive")),
            "tags": sorted(actor.get("tags") or []),
            "identity": json.dumps(actor.get("identity") or {}, sort_keys=True),
            "wanted": json.dumps(actor.get("wanted") or {}, sort_keys=True),
            "contacts": json.dumps(actor.get("contacts") or {}, sort_keys=True),
            "relations": json.dumps(actor.get("relations") or {}, sort_keys=True),
            "sources": json.dumps(actor.get("sources") or [], sort_keys=True),
        }
        actor["aliases"] = _split_csv(form.aliases.data)
        actor["bio"] = form.bio.data or ""
        actor["identity"] = {
            "first_name": form.first_name.data or "",
            "last_name": form.last_name.data or "",
            "age": form.age.data if form.age.data is not None else None,
            "dob": form.dob.data or "",
            "nationality": form.nationality.data or "",
            "location": form.location.data or "",
            "notes": form.id_notes.data or "",
        }
        actor["wanted"] = {
            "fbi": {"url": form.fbi_url.data or "", "id": actor.get("wanted", {}).get("fbi", {}).get("id", "")},
            "europol": {
                "url": form.europol_url.data or "",
                "id": actor.get("wanted", {}).get("europol", {}).get("id", ""),
            },
            "interpol": {
                "url": form.interpol_url.data or "",
                "id": actor.get("wanted", {}).get("interpol", {}).get("id", ""),
            },
        }
        srcs = []
        for line in _split_lines(form.sources.data):
            if "://" in line:
                if "—" in line:
                    title, url = line.split("—", 1)
                    srcs.append({"title": title.strip(), "url": url.strip()})
                else:
                    srcs.append({"url": line.strip()})
        actor["sources"] = srcs

        actor["contacts"] = {
            "jabber": _split_lines(form.jabber.data),
            "email": _split_lines(form.email.data),
            "pgp": _split_lines(form.pgp.data),
            "matrix": _split_lines(form.matrix.data),
            "session": _split_lines(form.session.data),
            "telegram": _split_lines(form.telegram.data),
            "tox": _split_lines(form.tox.data),
            "simplex": _split_lines(form.simplex.data),
            "max": _split_lines(form.max.data),
            "sonar": _split_lines(form.sonar.data),
            "x": _split_lines(form.x.data),
            "bluesky": _split_lines(form.bluesky.data),
        }
        actor["contacts"] = _normalize_contacts(actor["contacts"])
        old_rel = actor.get("relations") or {}
        old_groups = {_norm_key(x) for x in (old_rel.get("groups") or [])}
        old_forums = {_norm_key(x) for x in (old_rel.get("forums") or [])}
        old_peers = {_norm_key(p.get("name") if isinstance(p, dict) else str(p)) for p in (old_rel.get("peers") or [])}  # type: ignore[arg-type]

        actor["relations"] = {
            "groups": _split_csv(form.groups.data),
            "forums": _split_csv(form.forums.data),
            "peers": [{"name": p} for p in _split_csv(form.peers.data)],
        }
        actor["tags"] = _split_csv(form.tags.data)
        actor["private"] = bool(form.private.data)
        actor["noactive"] = bool(form.noactive.data)
        actor["updated_at"] = dt.utcnow().isoformat() + "Z"

        red.set(key, json.dumps(actor, ensure_ascii=False))
        # --- Backlinks (edit diffs) ---
        actor_name = actor["name"]
        self_key = _norm_key(actor_name)

        new_groups = {_norm_key(x) for x in (actor.get("relations", {}).get("groups") or [])}
        new_forums = {_norm_key(x) for x in (actor.get("relations", {}).get("forums") or [])}
        new_peers = {
            _norm_key(p.get("name") if isinstance(p, dict) else str(p))  # type: ignore[arg-type]
            for p in (actor.get("relations", {}).get("peers") or [])
        }
        new_peers.discard(self_key)

        added_groups = new_groups - old_groups
        removed_groups = old_groups - new_groups
        for g in added_groups:
            _set_group_affiliate(g, actor_name, True)
        for g in removed_groups:
            _set_group_affiliate(g, actor_name, False)

        added_forums = new_forums - old_forums
        removed_forums = old_forums - new_forums
        for f in added_forums:
            _set_market_affiliate(f, actor_name, True)
        for f in removed_forums:
            _set_market_affiliate(f, actor_name, False)

        added_peers = new_peers - old_peers - {self_key}
        removed_peers = (old_peers - new_peers) - {self_key}
        for p in added_peers:
            _set_peer_has_actor(p, actor_name, True)
        for p in removed_peers:
            _set_peer_has_actor(p, actor_name, False)

        _new_actor = {
            "aliases": sorted(actor.get("aliases") or []),
            "bio": actor.get("bio", ""),
            "private": bool(actor.get("private")),
            "noactive": bool(actor.get("noactive")),
            "tags": sorted(actor.get("tags") or []),
            "identity": json.dumps(actor.get("identity") or {}, sort_keys=True),
            "wanted": json.dumps(actor.get("wanted") or {}, sort_keys=True),
            "contacts": json.dumps(actor.get("contacts") or {}, sort_keys=True),
            "relations": json.dumps(actor.get("relations") or {}, sort_keys=True),
            "sources": json.dumps(actor.get("sources") or [], sort_keys=True),
        }
        _actor_changes = [k for k in _old_actor if _old_actor[k] != _new_actor.get(k)]
        if _actor_changes:
            _actor_details = []
            for k in _actor_changes:
                _actor_details.append(f"{k}: {_old_actor[k]!r} -> {_new_actor.get(k)!r}")
            audit_log("edit_actor", actor["name"], "; ".join(_actor_details))
        else:
            audit_log("edit_actor", actor["name"], "no changes")
        flash("Actor updated.", "success")
        return redirect(f"/admin/editactor/{quote(actor['name'])}")

    images_link = f"/admin/logo/5/{quote(actor.get('name', ''))}"
    return render_template(
        "admin/editactor.html",
        form=form,
        actor_name=actor.get("name", ""),
        images_link=images_link,
        groups_all=groups_all,
        markets_all=markets_all,
        peers_all=peers_all,
    )


@app.route("/admin/ransomnotes")
@flask_login.login_required
def admin_ransomnotes_index():  # type: ignore[no-untyped-def]
    r11 = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_NOTES)

    found = set()
    cursor = 0
    while True:
        cursor, keys = r11.scan(cursor=cursor, match="idx:group:*:notes", count=500)  # type: ignore[misc]
        for k in keys:
            k = k.decode()
            parts = k.split(":")
            if len(parts) >= 4 and r11.scard(k) > 0:  # type: ignore[operator]
                found.add(parts[2])
        if cursor == 0:
            break

    alias_to_canon = {}
    raw = r11.hgetall("alias:group") or {}
    for a, c in raw.items():  # type: ignore[union-attr]
        alias_to_canon[a.decode()] = c.decode()

    canon_to_aliases: dict[str, set[str]] = {}
    for alias, canon in alias_to_canon.items():
        canon_to_aliases.setdefault(canon, set()).add(alias)
    for c in list(found):
        als: Any = r11.smembers(f"group:{c}:aliases") or []
        if als:
            canon_to_aliases.setdefault(c, set()).update(x.decode() for x in als)

    canons = sorted({alias_to_canon.get(s, s) for s in found})

    data = [canons[i : i + 3] for i in range(0, len(canons), 3)]

    aliases_by_canon = {c: sorted(list(als)) for c, als in canon_to_aliases.items()}

    return render_template("admin/ransomnotes_index.html", data=data, aliases_by_canon=aliases_by_canon)


@app.route("/admin/ransomnotes/open", methods=["POST"])
@flask_login.login_required
def admin_ransomnotes_open():  # type: ignore[no-untyped-def]
    name = (request.form.get("group") or "").strip()
    if not name:
        flash("Please select a group name.", "warning")
        return redirect(url_for("admin_ransomnotes_index"))

    slug = _norm_group(name)

    return redirect(url_for("admin_ransomnotes_group", slug=slug))


@app.route("/admin/ransomnotes/<slug>")
@flask_login.login_required  # type: ignore[untyped-decorator]
def admin_ransomnotes_group(slug: str):  # type: ignore[no-untyped-def]
    r11 = _r11()
    canon = _norm_group(slug)
    mapped = r11.hget("alias:group", canon)
    if mapped:
        canon = mapped.decode()  # type: ignore[union-attr]

    aliases = sorted([a.decode() for a in (r11.smembers(f"group:{canon}:aliases") or [])])  # type: ignore[union-attr]

    idset_keys = [f"idx:group:{canon}:notes"] + [f"idx:group:{a}:notes" for a in aliases]
    note_ids = set()
    for k in idset_keys:
        for nid in r11.smembers(k):  # type: ignore[union-attr]
            note_ids.add(nid.decode())

    ids = list(note_ids)
    notes = []
    if ids:
        pipe = r11.pipeline()
        for i in ids:
            pipe.zscore("idx:notes:updated", i)
        scores = pipe.execute()  # type: ignore[no-untyped-call]
        ids_sorted = [x for _, x in sorted(zip(scores, ids), key=lambda t: t[0] or 0, reverse=True)]
        pipe = r11.pipeline()
        for i in ids_sorted:
            pipe.get(f"note:{i}")
        raws = pipe.execute()  # type: ignore[no-untyped-call]
        for b in raws:
            if not b:
                continue
            try:
                n = json.loads(b)
                notes.append(n)
            except Exception:
                pass

    return render_template("admin/ransomnotes_group.html", slug=canon, aliases=aliases, notes=notes)


# ---- Actions alias ----
@app.route("/admin/ransomnotes/<slug>/alias/add", methods=["POST"])
@flask_login.login_required  # type: ignore[untyped-decorator]
def admin_ransomnotes_alias_add(slug: str):  # type: ignore[no-untyped-def]
    r11 = _r11()
    canon = _norm_group(slug)
    alias = _norm_group(request.form.get("alias") or "")
    if not alias or alias == canon:
        flash("Alias invalide.", "warning")
        return redirect(url_for("admin_ransomnotes_group", slug=canon))
    r11.hset("alias:group", alias, canon)
    r11.sadd(f"group:{canon}:aliases", alias)
    audit_log("add_note_alias", canon, f"alias={alias}")
    flash(f"Alias '{alias}' added.", "success")
    return redirect(url_for("admin_ransomnotes_group", slug=canon))


@app.route("/admin/ransomnotes/<slug>/alias/<alias>/delete", methods=["POST"])
@flask_login.login_required  # type: ignore[untyped-decorator]
def admin_ransomnotes_alias_del(slug: str, alias: str):  # type: ignore[no-untyped-def]
    r11 = _r11()
    canon = _norm_group(slug)
    a = _norm_group(alias)
    r11.hdel("alias:group", a)
    r11.srem(f"group:{canon}:aliases", a)
    audit_log("delete_note_alias", canon, f"alias={a}")
    flash(f"Alias '{a}' deleted.", "success")
    return redirect(url_for("admin_ransomnotes_group", slug=canon))


# ---- Actions notes ----
@app.route("/admin/ransomnotes/<slug>/note/create", methods=["POST"])
@flask_login.login_required  # type: ignore[untyped-decorator]
def admin_ransomnotes_note_create(slug: str):  # type: ignore[no-untyped-def]
    r11 = _r11()
    canon = _norm_group(slug)

    title = (request.form.get("title") or "").strip()
    content = request.form.get("content") or ""
    fmt = (request.form.get("format") or "txt").strip().lower()
    status = (request.form.get("status") or "active").strip().lower()
    local_override = True if request.form.get("local_override") == "on" else False

    nid = uuid4().hex
    note = {
        "id": nid,
        "title": title or "note.txt",
        "content": content,
        "format": fmt if fmt in ("txt", "md", "html", "rtf") else "txt",
        "language": None,
        "groups": [canon],
        "sources": [{"kind": "manual"}],
        "external_uids": [],
        "checksum": _sha256(content),
        "status": status,
        "local_override": local_override or True,
        "pending_upstream": False,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "created_by": "admin",
        "updated_by": "admin",
    }
    _save_note(r11, note)
    audit_log("create_note", canon, f"title={note['title']}")
    flash("Note created.", "success")
    return redirect(url_for("admin_ransomnotes_group", slug=canon))


@app.route("/admin/ransomnotes/<slug>/note/<nid>/update", methods=["POST"])
@flask_login.login_required  # type: ignore[untyped-decorator]
def admin_ransomnotes_note_update(slug: str, nid: str):  # type: ignore[no-untyped-def]
    r11 = _r11()
    canon = _norm_group(slug)

    n = _load_note(r11, nid)
    if not n:
        flash("Note not found.", "danger")
        return redirect(url_for("admin_ransomnotes_group", slug=canon))

    _old_note = {
        "title": n.get("title", ""),
        "status": n.get("status", "active"),
        "format": n.get("format", "txt"),
        "content": n.get("content", ""),
        "local_override": n.get("local_override", False),
    }

    n["title"] = (request.form.get("title") or n.get("title") or "").strip()
    new_content = request.form.get("content")
    if new_content is not None and new_content != n.get("content", ""):
        n["content"] = new_content
        n["checksum"] = _sha256(new_content)
    old_status = _old_note["status"]
    old_format = _old_note["format"]
    new_fmt = (request.form.get("format") or n.get("format") or "txt").strip().lower()
    n["format"] = new_fmt if new_fmt in ("txt", "md", "html", "rtf") else "txt"
    n["status"] = (request.form.get("status") or n.get("status") or "active").strip().lower()
    n["local_override"] = True if request.form.get("local_override") == "on" else False
    n["updated_at"] = _now_iso()
    n["updated_by"] = "admin"

    if old_status != n["status"]:
        r11.srem(f"idx:status:{old_status}", n["id"])
    if old_format != n["format"]:
        r11.srem(f"idx:format:{old_format}", n["id"])

    _save_note(r11, n)
    _new_note = {
        "title": n.get("title", ""),
        "status": n.get("status", "active"),
        "format": n.get("format", "txt"),
        "content": n.get("content", ""),
        "local_override": n.get("local_override", False),
    }
    _note_changes = [k for k in _old_note if _old_note[k] != _new_note.get(k)]
    audit_log(
        "update_note",
        canon,
        f"id={nid}, changed={', '.join(_note_changes)}" if _note_changes else f"id={nid}, no changes",
    )
    flash("Note updated.", "success")
    return redirect(url_for("admin_ransomnotes_group", slug=canon))


@app.route("/admin/ransomnotes/<slug>/note/<nid>/delete", methods=["POST"])
@flask_login.login_required  # type: ignore[untyped-decorator]
def admin_ransomnotes_note_delete(slug: str, nid: str):  # type: ignore[no-untyped-def]
    r11 = _r11()
    canon = _norm_group(slug)

    n = _load_note(r11, nid)
    if not n:
        flash("Note not found.", "warning")
        return redirect(url_for("admin_ransomnotes_group", slug=canon))

    _remove_note(r11, n)
    audit_log("delete_note", canon, f"title={n.get('title', '')}, id={nid}")
    flash("Note deleted.", "success")
    return redirect(url_for("admin_ransomnotes_group", slug=canon))


######################################### Crypto admin
@app.route("/admin/crypto", methods=["GET"])
@flask_login.login_required
def admin_crypto():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    # alias -> canon
    alias_to_canon = {}
    cursor = 0
    while True:
        cursor, keys = red.scan(cursor=cursor, match="crypto:alias:*", count=500)  # type: ignore[misc]
        for akey in keys:
            tgt = red.get(akey)
            if tgt:
                alias_to_canon[akey.decode().split(":", 2)[-1]] = tgt.decode()  # type: ignore[union-attr]
        if cursor == 0:
            break

    # canon -> [alias]
    canon_to_aliases: dict[str, list[str]] = {}
    for a, c in alias_to_canon.items():
        canon_to_aliases.setdefault(c, []).append(a)
    for c in list(canon_to_aliases.keys()):
        canon_to_aliases[c].sort()

    groups = []
    cursor = 0
    seen = set()
    while True:
        cursor, keys = red.scan(cursor=cursor, match="idx:group:*:crypto", count=500)  # type: ignore[misc]
        for k in keys:
            k_dec = k.decode()  # idx:group:<canon>:crypto
            parts = k_dec.split(":")
            if len(parts) >= 4:
                canon = parts[2]
                if canon in seen:
                    continue
                cnt = red.scard(k)
                seen.add(canon)
                groups.append({"name": canon, "count": cnt, "aliases": canon_to_aliases.get(canon, [])})
        if cursor == 0:
            break

    groups.sort(key=lambda x: x["name"])
    return render_template("admin/crypto.html", groups=groups)


@app.route("/admin/crypto/<group>", methods=["GET"])
@flask_login.login_required
def admin_crypto_group(group):  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    # Resolve canon DB=7 (alias -> canon, else keep provided)
    alias_norm = re.sub(r"[^a-z0-9]+", "", (group or "").lower())
    raw = red.get("crypto:alias:" + alias_norm)
    canon = raw.decode() if raw else (group or "").strip() or "Unknwn"  # type: ignore[union-attr]

    members = red.smembers(f"idx:group:{canon}:crypto") or set()
    by_chain: dict[str, Any] = {}
    for it in members:  # type: ignore[union-attr]
        ca = it.decode()
        if ":" not in ca:
            continue
        chain, addr = ca.split(":", 1)
        raw = red.get(f"crypto:addr:{chain}:{addr}")
        if not raw:
            continue
        try:
            doc = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            continue
        doc.setdefault("address", addr)
        doc.setdefault("source", "unknown")
        doc.setdefault("transactions", [])
        doc["tx_count"] = doc.get("tx_count") or len(doc["transactions"])
        by_chain.setdefault(chain, []).append(doc)

    for ch, lst in by_chain.items():
        lst.sort(key=lambda x: (x.get("tx_count", 0), x.get("last_tx_time") or 0), reverse=True)
    by_chain = dict(sorted(by_chain.items(), key=lambda kv: kv[0]))

    return render_template("admin/crypto_group.html", group=canon, by_chain=by_chain)


@app.route("/admin/crypto/group/new", methods=["GET", "POST"])
def admin_crypto_group_new():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    if request.method == "POST":
        canon = (request.form.get("canon") or "").strip()
        display_name = (request.form.get("display_name") or "").strip()
        aliases_raw = (request.form.get("aliases") or "").strip()

        if not canon:
            flash("Canonical name is required.", "danger")
            return redirect(url_for("admin_crypto_group_new"))

        if display_name:
            now = dt.now(timezone.utc).isoformat().replace("+00:00", "Z")
            red.set(f"crypto:group:{canon}:meta", json.dumps({"display_name": display_name, "created_at": now}))

        if aliases_raw:
            for alias in [a.strip() for a in aliases_raw.split(",") if a.strip()]:
                alias_norm = re.sub(r"[^a-z0-9]+", "", alias.lower())
                if alias_norm:
                    red.set(f"crypto:alias:{alias_norm}", canon)

        audit_log("add_crypto_group", canon, f"aliases={aliases_raw}")
        flash("Group created in DB=7.", "success")
        return redirect(url_for("admin_crypto_group", group=canon))

    return render_template("admin/crypto_group_new.html")


@app.route("/admin/crypto/<group>/address/new", methods=["GET", "POST"])
@flask_login.login_required
def admin_crypto_new(group):  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    alias_norm = re.sub(r"[^a-z0-9]+", "", (group or "").lower())
    raw = red.get("crypto:alias:" + alias_norm)
    canon = raw.decode() if raw else (group or "").strip() or "Unknwn"  # type: ignore[union-attr]

    if request.method == "POST":
        chain = (request.form.get("blockchain") or "bitcoin").strip().lower()
        addr = (request.form.get("address") or "").strip()
        src = (request.form.get("source") or "manual").strip()
        label = (request.form.get("label") or "").strip()
        txs_raw = request.form.get("transactions") or "[]"

        if not addr:
            flash("Address is required.", "danger")
            return redirect(url_for("admin_crypto_new", group=group))

        try:
            txs = json.loads(txs_raw)
            if not isinstance(txs, list):
                raise ValueError("transactions must be JSON array")
            for t in txs:
                if isinstance(t, dict) and (not t.get("source")):
                    t["source"] = src
        except Exception as e:
            flash(f"Invalid transactions JSON: {e}", "danger")
            return redirect(url_for("admin_crypto_new", group=group))

        now = dt.now(timezone.utc).isoformat().replace("+00:00", "Z")
        key = f"crypto:addr:{chain}:{addr}"

        doc = {
            "group": canon,
            "address": addr,
            "blockchain": chain,
            "source": src,
            "origin": "manual",
            "label": label or None,
            "transactions": txs,
            "tx_count": len(txs),
            "last_tx_time": max(
                [str(t.get("time")) for t in txs if isinstance(t, dict) and t.get("time") is not None], default=None
            ),  # type: ignore[type-var]
            "created_at": now,
            "updated_at": now,
        }

        red.set(key, json.dumps(doc, ensure_ascii=False))
        red.sadd(f"idx:group:{canon}:crypto", f"{chain}:{addr}")
        red.sadd(f"idx:group:{canon}:crypto:{chain}", addr)
        red.sadd(f"idx:source:{src}:crypto", f"{chain}:{addr}")

        audit_log("add_crypto_addr", canon, f"chain={chain}, addr={addr}")
        flash("Address created.", "success")
        return redirect(url_for("admin_crypto_group", group=group))

    return render_template("admin/crypto_addr_form.html", mode="new", group=group, blockchain="", address="", doc={})


@app.route("/admin/crypto/<group>/address/<chain>/<addr>", methods=["GET", "POST"])
@flask_login.login_required
def admin_crypto_edit_addr(group, chain, addr):  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    key = f"crypto:addr:{chain}:{addr}"
    doc = {}
    raw = red.get(key)
    if raw:
        try:
            doc = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            doc = {}

    alias_norm = re.sub(r"[^a-z0-9]+", "", (group or "").lower())
    got = red.get("crypto:alias:" + alias_norm)
    canon = got.decode() if got else (group or "").strip() or "Unknwn"  # type: ignore[union-attr]

    _old_crypto = {
        "source": doc.get("source", ""),
        "label": doc.get("label") or "",
        "tx_count": doc.get("tx_count", 0),
    }

    if request.method == "POST":
        if (request.form.get("action") or "") == "delete":
            src = (doc.get("source") or "unknown") if doc else "unknown"
            red.srem(f"idx:group:{canon}:crypto", f"{chain}:{addr}")
            red.srem(f"idx:group:{canon}:crypto:{chain}", addr)
            red.srem(f"idx:source:{src}:crypto", f"{chain}:{addr}")
            red.delete(key)
            audit_log("delete_crypto_addr", canon, f"chain={chain}, addr={addr}")
            flash("Address deleted.", "success")
            return redirect(url_for("admin_crypto_group", group=group))

        src = (request.form.get("source") or doc.get("source") or "manual").strip()
        label = (request.form.get("label") or doc.get("label") or "").strip()
        txs_raw = request.form.get("transactions") or (json.dumps(doc.get("transactions") or []))

        try:
            txs = json.loads(txs_raw)
            if not isinstance(txs, list):
                raise ValueError("transactions must be JSON array")
            for t in txs:
                if isinstance(t, dict) and (not t.get("source")):
                    t["source"] = src
        except Exception as e:
            flash(f"Invalid transactions JSON: {e}", "danger")
            return redirect(url_for("admin_crypto_edit_addr", group=group, chain=chain, addr=addr))

        now = dt.now(timezone.utc).isoformat().replace("+00:00", "Z")
        created_at = doc.get("created_at") or now

        newdoc = dict(doc)
        newdoc.update(
            {
                "source": src,
                "label": label or None,
                "transactions": txs,
                "tx_count": len(txs),
                "last_tx_time": max(
                    [str(t.get("time")) for t in txs if isinstance(t, dict) and t.get("time") is not None], default=None
                ),  # type: ignore[type-var]
                "updated_at": now,
                "created_at": created_at,
                "group": canon,
                "address": addr,
                "blockchain": chain,
            }
        )

        red.set(key, json.dumps(newdoc, ensure_ascii=False))
        red.sadd(f"idx:group:{canon}:crypto", f"{chain}:{addr}")
        red.sadd(f"idx:group:{canon}:crypto:{chain}", addr)
        red.sadd(f"idx:source:{src}:crypto", f"{chain}:{addr}")

        _new_crypto = {
            "source": newdoc.get("source", ""),
            "label": newdoc.get("label") or "",
            "tx_count": newdoc.get("tx_count", 0),
        }
        _crypto_changes = [k for k in _old_crypto if _old_crypto[k] != _new_crypto.get(k)]
        audit_log(
            "edit_crypto_addr",
            canon,
            f"chain={chain}, addr={addr}, changed={', '.join(_crypto_changes)}"
            if _crypto_changes
            else f"chain={chain}, addr={addr}, no changes",
        )
        flash("Address updated.", "success")
        return redirect(url_for("admin_crypto_group", group=group))

    return render_template(
        "admin/crypto_addr_form.html", mode="edit", group=group, blockchain=chain, address=addr, doc=doc
    )


@app.route("/admin/crypto/aliases", methods=["GET", "POST"])
@flask_login.login_required
def admin_crypto_aliases():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

    if request.method == "POST":
        action = (request.form.get("action") or "upsert").strip()
        alias = (request.form.get("alias") or "").strip().lower()
        canon = (request.form.get("canon") or "").strip().lower()

        if not alias:
            flash("Alias is required.", "danger")
            return redirect(url_for("admin_crypto_aliases"))

        alias_norm = re.sub(r"[^a-z0-9]+", "", alias)

        if action == "delete":
            red.delete("crypto:alias:" + alias_norm)
            audit_log("delete_crypto_alias", alias_norm)
            flash("Alias deleted.", "success")
            return redirect(url_for("admin_crypto_aliases"))

        if not canon:
            flash("Canonical slug is required.", "danger")
            return redirect(url_for("admin_crypto_aliases"))

        red.set("crypto:alias:" + alias_norm, canon)
        audit_log("set_crypto_alias", alias_norm, f"canon={canon}")
        flash("Alias saved.", "success")
        return redirect(url_for("admin_crypto_aliases"))

    # GET
    rows = []
    cursor = 0
    while True:
        cursor, keys = red.scan(cursor=cursor, match="crypto:alias:*", count=500)  # type: ignore[misc]
        for k in keys:
            alias_norm = k.decode().split(":", 2)[-1]
            tgt = red.get(k)
            if tgt:
                rows.append({"alias": alias_norm, "canon": tgt.decode()})  # type: ignore[union-attr]
        if cursor == 0:
            break
    rows.sort(key=lambda x: (x["canon"], x["alias"]))
    return render_template("admin/crypto_aliases.html", aliases=rows)


############ URL manager


@app.route("/admin/urls", methods=["GET", "POST"])
@flask_login.login_required
def admin_urls():  # type: ignore[no-untyped-def]
    red_g = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    red_m = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    groups = sorted([k.decode() for k in red_g.keys()], key=str.lower)  # type: ignore[union-attr]
    markets = sorted([k.decode() for k in red_m.keys()], key=str.lower)  # type: ignore[union-attr]

    results = []

    if request.method == "POST":
        db_val = int(request.form.get("database", 0))
        name = (request.form.get("name") or "").strip().lower()
        url_type = request.form.get("url_type", "dls")
        browser = request.form.get("browser", "") or ""
        init_script = request.form.get("init_script", "") or ""
        raw_urls = request.form.get("urls", "")

        fs = url_type == "fs"
        chat = url_type == "chat"
        is_admin = url_type == "admin"
        private = bool(request.form.get("private"))

        if not name:
            flash("Group/market name is required.", "error")
        else:
            # Check that the group/market already exists
            red_check = Valkey(unix_socket_path=get_socket_path("cache"), db=db_val)
            if not red_check.exists(name):
                flash(f'"{name}" does not exist. Create it first.', "error")
                return redirect(url_for("admin_urls"))

            urls = [u.strip() for u in raw_urls.splitlines() if u.strip()]
            if not urls:
                flash("At least one URL is required.", "error")
            else:
                for url in urls:
                    res = adder(name, url, db_val, fs, private, chat, is_admin, browser or None, init_script or None)
                    ok = res < 2
                    results.append({"url": url, "ok": ok})
                    if ok:
                        audit_log(
                            "add_url", name, f"db={'group' if db_val == 0 else 'market'}, type={url_type}, url={url}"
                        )

                added = sum(1 for r in results if r["ok"])
                dupes = sum(1 for r in results if not r["ok"])
                if added:
                    flash(f"{added} URL(s) added to {name}.", "success")
                if dupes:
                    flash(f"{dupes} URL(s) already existed (skipped).", "warning")

    return render_template("admin/urls.html", groups=groups, markets=markets, results=results)


############ config editor

# Keys excluded from the config editor
_CONFIG_HIDDEN = {"users", "_notes", "logos"}


def _load_config_file() -> tuple[dict[str, Any], Any, bool]:
    """Load generic.json (or .sample fallback) and return (dict, path, is_sample)."""
    config_dir = get_homedir() / "config"
    real = config_dir / "generic.json"
    sample = config_dir / "generic.json.sample"
    if real.exists():
        with real.open(encoding="utf-8") as f:
            return json.load(f), real, False
    with sample.open(encoding="utf-8") as f:
        return json.load(f), sample, True


def _save_config_file(data: dict[str, Any]) -> None:
    """Write generic.json and invalidate the in-memory config cache."""
    from ransomlook.default.config import configs as _cfg_cache

    config_dir = get_homedir() / "config"
    path = config_dir / "generic.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    # invalidate cached configs so get_config() picks up changes
    _cfg_cache.clear()


@app.route("/admin/config", methods=["GET", "POST"])
@flask_login.login_required
def admin_config():  # type: ignore[no-untyped-def]
    cfg, cfg_path, is_sample = _load_config_file()

    # dynamically split keys into sections (dicts) vs scalars
    sections = []  # [{"key": k, "data": {...}}, ...]
    scalars = []  # [{"key": k, "value": v}, ...]
    for k, v in cfg.items():
        if k in _CONFIG_HIDDEN:
            continue
        if isinstance(v, dict):
            sections.append({"key": k, "data": v})
        else:
            scalars.append({"key": k, "value": v})

    if request.method == "POST":
        old_cfg = json.loads(json.dumps(cfg))  # deep copy
        changes = []

        # process object sections
        for sec in sections:
            k = sec["key"]  # type: ignore[assignment]
            for field in list(cfg[k].keys()):
                form_key = f"{k}.{field}"
                old_val = cfg[k][field]
                # booleans: unchecked checkbox is absent from form
                if isinstance(old_val, bool):
                    new_val = "on" in request.form.getlist(form_key)
                    if new_val != old_val:
                        changes.append(f"{k}.{field}")
                    cfg[k][field] = new_val
                    continue
                if form_key not in request.form:
                    continue
                raw = request.form[form_key]
                if isinstance(old_val, int):
                    try:
                        new_val = int(raw)  # type: ignore[assignment]
                    except ValueError:
                        new_val = raw
                elif isinstance(old_val, list):
                    new_val = [x.strip() for x in raw.split(",") if x.strip()]  # type: ignore[assignment]
                else:
                    new_val = raw
                if new_val != old_val:
                    changes.append(f"{k}.{field}")
                cfg[k][field] = new_val

        # process scalar fields
        for sc in scalars:
            k = sc["key"]
            old_val = cfg.get(k, "")
            if isinstance(old_val, bool):
                new_val = "on" in request.form.getlist(k)
            elif isinstance(old_val, int):
                try:
                    new_val = int(request.form.get(k, old_val))  # type: ignore[assignment]
                except (ValueError, TypeError):
                    new_val = old_val  # type: ignore[assignment]
            elif isinstance(old_val, float):
                try:
                    new_val = float(request.form.get(k, old_val))  # type: ignore[assignment]
                except (ValueError, TypeError):
                    new_val = old_val  # type: ignore[assignment]
            else:
                new_val = request.form.get(k, old_val)
            if new_val != old_val:
                changes.append(k)
            cfg[k] = new_val

        # preserve hidden keys untouched
        for hk in _CONFIG_HIDDEN:
            cfg[hk] = old_cfg.get(hk, {} if hk != "logos" else {})

        _save_config_file(cfg)
        audit_log("edit_config", "generic.json", ", ".join(changes) if changes else "no changes")
        flash("Configuration saved.", "success")
        return redirect(url_for("admin_config"))

    return render_template("admin/config.html", cfg=cfg, sections=sections, scalars=scalars, is_sample=is_sample)


############ API Keys


@app.route("/admin/apikeys", methods=["GET"])
@flask_login.login_required
def admin_apikeys():  # type: ignore[no-untyped-def]
    red = _get_apikeys_redis()
    raw = red.hgetall("apikeys") or {}
    keys = []
    for token, meta_raw in raw.items():  # type: ignore[union-attr]
        token_str = token.decode()
        try:
            meta = json.loads(meta_raw)
        except Exception:
            meta = {}
        keys.append(
            {
                "token": token_str,
                "token_short": token_str[:8] + "…" + token_str[-8:],
                "name": meta.get("name", ""),
                "created_at": meta.get("created_at", ""),
                "created_by": meta.get("created_by", ""),
                "last_used": meta.get("last_used", ""),
                "active": meta.get("active", True),
            }
        )
    keys.sort(key=lambda x: x["name"].lower())
    return render_template("admin/apikeys.html", keys=keys)


@app.route("/admin/apikeys/add", methods=["POST"])
@flask_login.login_required
def admin_apikeys_add():  # type: ignore[no-untyped-def]
    import secrets

    name = (request.form.get("name") or "").strip()
    if not name:
        flash("A name / comment is required.", "error")
        return redirect(url_for("admin_apikeys"))
    token = secrets.token_hex(32)  # 64 chars
    meta = {
        "name": name,
        "created_at": dt.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "created_by": flask_login.current_user.id,
        "last_used": "",
        "active": True,
    }
    red = _get_apikeys_redis()
    red.hset("apikeys", token, json.dumps(meta, ensure_ascii=False))
    audit_log("add_apikey", name, f"token={token[:8]}…")
    flash(f"API key created. Token (copy it now, it won't be shown again): {token}", "success")
    return redirect(url_for("admin_apikeys"))


@app.route("/admin/apikeys/toggle", methods=["POST"])
@flask_login.login_required
def admin_apikeys_toggle():  # type: ignore[no-untyped-def]
    token = request.form.get("token", "").strip()
    if not token:
        flash("Missing token.", "error")
        return redirect(url_for("admin_apikeys"))
    red = _get_apikeys_redis()
    raw = red.hget("apikeys", token)
    if not raw:
        flash("Key not found.", "error")
        return redirect(url_for("admin_apikeys"))
    meta = json.loads(raw)  # type: ignore[arg-type]
    meta["active"] = not meta.get("active", True)
    red.hset("apikeys", token, json.dumps(meta, ensure_ascii=False))
    state = "enabled" if meta["active"] else "disabled"
    audit_log("toggle_apikey", meta.get("name", ""), state)
    flash(f'Key "{meta.get("name", "")}" {state}.', "success")
    return redirect(url_for("admin_apikeys"))


@app.route("/admin/apikeys/delete", methods=["POST"])
@flask_login.login_required
def admin_apikeys_delete():  # type: ignore[no-untyped-def]
    token = request.form.get("token", "").strip()
    if not token:
        flash("Missing token.", "error")
        return redirect(url_for("admin_apikeys"))
    red = _get_apikeys_redis()
    raw = red.hget("apikeys", token)
    name = ""
    if raw:
        try:
            name = json.loads(raw).get("name", "")  # type: ignore[arg-type]
        except Exception:
            pass
    red.hdel("apikeys", token)
    audit_log("delete_apikey", name)
    flash(f'Key "{name}" deleted.', "success")
    return redirect(url_for("admin_apikeys"))


############ logs


@app.route("/admin/logs")
@flask_login.login_required
def logs():  # type: ignore[no-untyped-def]
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
    per_page = 50
    page = max(1, int(request.args.get("page", 1)))
    total = red.zcard("audit")
    start = (page - 1) * per_page
    end = start + per_page - 1
    raw = red.zrevrange("audit", start, end)
    entries = []
    users_set = set()
    actions_set = set()
    for r in raw:  # type: ignore[union-attr]
        try:
            e = json.loads(r.decode())
        except Exception:
            continue
        users_set.add(e.get("user", ""))
        actions_set.add(e.get("action", ""))
        entries.append(e)
    total_pages = max(1, (total + per_page - 1) // per_page)  # type: ignore[operator]

    # also read legacy "logs" key if it exists (migration)
    legacy_count = red.zcard("logs")

    return render_template(
        "admin/logs.html",
        entries=entries,
        page=page,
        total_pages=total_pages,
        total=total,
        legacy_count=legacy_count,
        users=sorted(users_set),
        actions=sorted(actions_set),
    )


@app.route("/admin/alerting", methods=["GET", "POST"])
@flask_login.login_required
def alerting():  # type: ignore[no-untyped-def]
    form = AlertForm()
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
    keywordsred = red.get("keywords")
    keywords = None
    if keywordsred is not None:
        keywords = keywordsred.decode()  # type: ignore[union-attr]
    if form.validate_on_submit():
        old_set = set(filter(None, (keywords or "").splitlines()))
        keywordstmp = str(form.keywords.data).splitlines()
        keywordslist = list(dict.fromkeys(keywordstmp))
        new_set = set(filter(None, keywordslist))
        added = sorted(new_set - old_set)
        removed = sorted(old_set - new_set)
        keywords = "\n".join(keywordslist)
        red.set("keywords", str(keywords))
        parts = []
        if added:
            parts.append(f"added={', '.join(added)}")
        if removed:
            parts.append(f"removed={', '.join(removed)}")
        if not parts:
            parts.append("no changes")
        audit_log("update_keywords", "alerting", "; ".join(parts))
        flash("Success to update keywords", "success")
    form.keywords.data = keywords
    return render_template("admin/alerts.html", form=form)


if __name__ == "__main__":
    app.run()


authorizations = {"apikey": {"type": "apiKey", "in": "header", "name": "Authorization"}}

api = Api(
    app,
    title="RansomLook API",
    description="API to query a RansomLook instance.",
    doc="/doc/",
    authorizations=authorizations,
    version=pkg_version,
)

api.add_namespace(stats_api)
api.add_namespace(generic_api)
api.add_namespace(actors_api)
api.add_namespace(crypto_api)
api.add_namespace(notes_api)
api.add_namespace(leaks_api)
api.add_namespace(rf_api)


@app.route("/groups.csv")
def groups_csv():  # type: ignore[no-untyped-def]
    raw = (request.args.get("status") or "all").lower()
    if raw in {"active", "up"}:
        status_filter = "actif"
    elif raw in {"inactive", "down"}:
        status_filter = "inactif"
    elif raw in {"actif", "inactif"}:
        status_filter = raw
    else:
        status_filter = "all"

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)

    rows = []
    for key in red.keys():  # type: ignore[union-attr]
        entry = json.loads(red.get(key))  # type: ignore[arg-type]
        if not current_user.is_authenticated and entry.get("private") is True:
            continue
        name = key.decode()
        for loc in entry.get("locations", []):
            if not current_user.is_authenticated and loc.get("private") is True:
                continue

            available = bool(loc.get("available"))
            if status_filter == "actif" and not available:
                continue
            if status_filter == "inactif" and available:
                continue

            date_str = str(loc.get("lastscrape", "")).split(" ")[0] if loc.get("lastscrape") else ""

            row = [name, loc.get("slug", ""), "active" if available else "inactive", date_str]
            if current_user.is_authenticated:
                row.append("yes" if bool(loc.get("private")) else "no")
            row.append(loc.get("title", "") or "")
            rows.append(row)

    rows.sort(key=lambda r: (_norm_for_sort(r[0]), _norm_for_sort(r[1])))

    sio = StringIO()
    writer = csv.writer(sio)
    headers = ["Name", "URL", "Status", "Date"] + (["Private"] if current_user.is_authenticated else []) + ["PageTitle"]
    writer.writerow(headers)
    writer.writerows(rows)

    resp = Response(sio.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = "attachment; filename=groups_urls.csv"
    return resp


@app.route("/group/<name>/urls.csv")
def group_urls_csv(name: str):  # type: ignore[no-untyped-def]
    raw = (request.args.get("status") or "all").lower()
    if raw in {"active", "up"}:
        status_filter = "actif"
    elif raw in {"inactive", "down"}:
        status_filter = "inactif"
    elif raw in {"actif", "inactif"}:
        status_filter = raw
    else:
        status_filter = "all"

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)

    target = None
    for key in red.keys():  # type: ignore[union-attr]
        if key.decode().lower() == name.lower():
            target = (key, json.loads(red.get(key)))  # type: ignore[arg-type]
            break

    if not target:
        return redirect(url_for("home"))

    key, entry = target
    if not current_user.is_authenticated and entry.get("private") is True:
        return redirect(url_for("home"))

    rows = []
    headers = ["URL", "Type", "Status", "Date"] + (["Private"] if current_user.is_authenticated else []) + ["PageTitle"]
    for loc in entry.get("locations", []):
        if not current_user.is_authenticated and loc.get("private") is True:
            continue

        available = bool(loc.get("available"))
        if status_filter == "actif" and not available:
            continue
        if status_filter == "inactif" and available:
            continue

        date_str = str(loc.get("lastscrape", "")).split(" ")[0] if loc.get("lastscrape") else ""
        link_type = "FS" if loc.get("fs") else ("Chat" if loc.get("chat") else ("Admin" if loc.get("admin") else "DLS"))

        row = [loc.get("slug", ""), link_type, "active" if available else "inactive", date_str]
        if current_user.is_authenticated:
            row.append("yes" if bool(loc.get("private")) else "no")
        row.append(loc.get("title", "") or "")
        rows.append(row)

    rows.sort(key=lambda r: (_norm_for_sort(r[1]), _norm_for_sort(r[0])))

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(headers)
    writer.writerows(rows)

    safe_name = key.decode().replace("/", "_")
    resp = Response(sio.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename={safe_name}_urls.csv"
    return resp


@app.route("/markets.csv")
def markets_csv():  # type: ignore[no-untyped-def]
    raw = (request.args.get("status") or "all").lower()
    if raw in {"active", "up"}:
        status_filter = "actif"
    elif raw in {"inactive", "down"}:
        status_filter = "inactif"
    elif raw in {"actif", "inactif"}:
        status_filter = raw
    else:
        status_filter = "all"

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)

    rows = []
    for key in red.keys():  # type: ignore[union-attr]
        entry = json.loads(red.get(key))  # type: ignore[arg-type]
        if not current_user.is_authenticated and entry.get("private") is True:
            continue
        name = key.decode()
        for loc in entry.get("locations", []):
            if not current_user.is_authenticated and loc.get("private") is True:
                continue

            available = bool(loc.get("available"))
            if status_filter == "actif" and not available:
                continue
            if status_filter == "inactif" and available:
                continue

            date_str = str(loc.get("lastscrape", "")).split(" ")[0] if loc.get("lastscrape") else ""

            row = [name, loc.get("slug", ""), "active" if available else "inactive", date_str]
            if current_user.is_authenticated:
                row.append("yes" if bool(loc.get("private")) else "no")
            row.append(loc.get("title", "") or "")
            rows.append(row)

    rows.sort(key=lambda r: (_norm_for_sort(r[0]), _norm_for_sort(r[1])))

    sio = StringIO()
    writer = csv.writer(sio)
    headers = ["Name", "URL", "Status", "Date"] + (["Private"] if current_user.is_authenticated else []) + ["PageTitle"]
    writer.writerow(headers)
    writer.writerows(rows)

    resp = Response(sio.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = "attachment; filename=markets_urls.csv"
    return resp


@app.route("/market/<name>/urls.csv")
def market_urls_csv(name: str):  # type: ignore[no-untyped-def]
    raw = (request.args.get("status") or "all").lower()
    if raw in {"active", "up"}:
        status_filter = "actif"
    elif raw in {"inactive", "down"}:
        status_filter = "inactif"
    elif raw in {"actif", "inactif"}:
        status_filter = raw
    else:
        status_filter = "all"

    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)

    target = None
    for key in red.keys():  # type: ignore[union-attr]
        if key.decode().lower() == name.lower():
            target = (key, json.loads(red.get(key)))  # type: ignore[arg-type]
            break

    if not target:
        return redirect(url_for("home"))

    key, entry = target
    if not current_user.is_authenticated and entry.get("private") is True:
        return redirect(url_for("home"))

    rows = []
    headers = ["URL", "Type", "Status", "Date"] + (["Private"] if current_user.is_authenticated else []) + ["PageTitle"]
    for loc in entry.get("locations", []):
        if not current_user.is_authenticated and loc.get("private") is True:
            continue

        available = bool(loc.get("available"))
        if status_filter == "actif" and not available:
            continue
        if status_filter == "inactif" and available:
            continue

        date_str = str(loc.get("lastscrape", "")).split(" ")[0] if loc.get("lastscrape") else ""
        link_type = "FS" if loc.get("fs") else ("Chat" if loc.get("chat") else ("Admin" if loc.get("admin") else "DLS"))

        row = [loc.get("slug", ""), link_type, "active" if available else "inactive", date_str]
        if current_user.is_authenticated:
            row.append("yes" if bool(loc.get("private")) else "no")
        row.append(loc.get("title", "") or "")
        rows.append(row)

    rows.sort(key=lambda r: (_norm_for_sort(r[1]), _norm_for_sort(r[0])))

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(headers)
    writer.writerows(rows)

    safe_name = key.decode().replace("/", "_")
    resp = Response(sio.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename={safe_name}_urls.csv"
    return resp


@app.route("/group/<name>/posts.csv")
def group_posts_csv(name: str):  # type: ignore[no-untyped-def]
    base_red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)
    entry = None
    key_bytes = None
    for k in base_red.keys():  # type: ignore[union-attr]
        if k.decode().lower() == name.lower():
            key_bytes = k
            entry = json.loads(base_red.get(k))  # type: ignore[arg-type]
            break
    if entry is None:
        return redirect(url_for("home"))
    if not current_user.is_authenticated and entry.get("private") is True:
        return redirect(url_for("home"))

    # Optional date filters (?from=YYYY-MM-DD&to=YYYY-MM-DD)
    from_str = request.args.get("from") or request.args.get("date_from") or request.args.get("start")
    to_str = request.args.get("to") or request.args.get("date_to") or request.args.get("end")

    def _parse_dt(val: Any) -> tuple[Any, Any]:
        if not val:
            return None, val
        try:
            return parser.parse(val), val
        except Exception:
            return None, val

    dt_from, from_raw = _parse_dt(from_str)
    dt_to, to_raw = _parse_dt(to_str)
    if (
        dt_to
        and to_raw
        and (" " not in to_raw and "T" not in to_raw)
        and dt_to.hour == 0
        and dt_to.minute == 0
        and dt_to.second == 0
        and dt_to.microsecond == 0
    ):
        dt_to = dt_to + timedelta(days=1) - timedelta(seconds=1)

    redpost = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
    rows = []
    if key_bytes in redpost.keys():  # type: ignore[operator]
        posts = json.loads(redpost.get(key_bytes))  # type: ignore[arg-type]
        posts.sort(key=lambda x: x.get("discovered", ""), reverse=True)
        for post in posts:
            date_str = ""
            disc_dt = None
            if post.get("discovered"):
                disc_str = str(post["discovered"])
                date_str = disc_str.split(" ")[0]
                try:
                    disc_dt = parser.parse(disc_str)
                except Exception:
                    disc_dt = None
            if dt_from and (not disc_dt or disc_dt < dt_from):
                continue
            if dt_to and (not disc_dt or disc_dt > dt_to):
                continue

            title = post.get("post_title", "") or post.get("title", "") or ""
            desc = post.get("description", "") or ""
            rows.append([date_str, title, desc])

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(["Date", "Title", "Description"])
    writer.writerows(rows)

    safe_name = key_bytes.decode().replace("/", "_")  # type: ignore[union-attr]
    resp = Response(sio.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename={safe_name}_posts.csv"
    return resp


@app.route("/market/<name>/posts.csv")
def market_posts_csv(name: str):  # type: ignore[no-untyped-def]
    base_red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)
    entry = None
    key_bytes = None
    for k in base_red.keys():  # type: ignore[union-attr]
        if k.decode().lower() == name.lower():
            key_bytes = k
            entry = json.loads(base_red.get(k))  # type: ignore[arg-type]
            break
    if entry is None:
        return redirect(url_for("home"))
    if not current_user.is_authenticated and entry.get("private") is True:
        return redirect(url_for("home"))

    from_str = request.args.get("from") or request.args.get("date_from") or request.args.get("start")
    to_str = request.args.get("to") or request.args.get("date_to") or request.args.get("end")

    def _parse_dt(val: Any) -> tuple[Any, Any]:
        if not val:
            return None, val
        try:
            return parser.parse(val), val
        except Exception:
            return None, val

    dt_from, from_raw = _parse_dt(from_str)
    dt_to, to_raw = _parse_dt(to_str)
    if (
        dt_to
        and to_raw
        and (" " not in to_raw and "T" not in to_raw)
        and dt_to.hour == 0
        and dt_to.minute == 0
        and dt_to.second == 0
        and dt_to.microsecond == 0
    ):
        dt_to = dt_to + timedelta(days=1) - timedelta(seconds=1)

    redpost = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
    rows = []
    if key_bytes in redpost.keys():  # type: ignore[operator]
        posts = json.loads(redpost.get(key_bytes))  # type: ignore[arg-type]
        posts.sort(key=lambda x: x.get("discovered", ""), reverse=True)
        for post in posts:
            date_str = ""
            disc_dt = None
            if post.get("discovered"):
                disc_str = str(post["discovered"])
                date_str = disc_str.split(" ")[0]
                try:
                    disc_dt = parser.parse(disc_str)
                except Exception:
                    disc_dt = None
            if dt_from and (not disc_dt or disc_dt < dt_from):
                continue
            if dt_to and (not disc_dt or disc_dt > dt_to):
                continue

            title = post.get("post_title", "") or post.get("title", "") or ""
            desc = post.get("description", "") or ""
            rows.append([date_str, title, desc])

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(["Date", "Title", "Description"])
    writer.writerows(rows)

    safe_name = key_bytes.decode().replace("/", "_")  # type: ignore[union-attr]
    resp = Response(sio.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename={safe_name}_posts.csv"
    return resp


@app.route("/compare", methods=["GET"])
def compare():  # type: ignore[no-untyped-def]
    from urllib.parse import urlparse

    # --- type d’entrée ---
    kind = (request.args.get("kind") or "group").strip().lower()
    if kind not in ("group", "market"):
        kind = "group"

    # --- sélection A/B (querystring) ---
    name_a = (request.args.get("a") or "").strip()
    name_b = (request.args.get("b") or "").strip()

    # --- auto-préselection depuis le referer si A vide ---
    if not name_a:
        ref = request.headers.get("Referer") or ""
        try:
            path = urlparse(ref).path  # ex: /group/0mega
            m = re.match(r"^/(group|market)/([^/]+)$", path)
            if m:
                ref_kind, ref_name = m.group(1), m.group(2)
                # bascule auto du "kind" si pas fourni explicitement
                if "kind" not in request.args:
                    kind = "group" if ref_kind == "group" else "market"
                name_a = ref_name
        except Exception:
            pass

    # connexions Redis
    red_groups = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)  # groupes
    red_markets = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)  # markets/forums
    red_posts = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)  # posts

    try:
        red_health = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_HEALTH)
    except Exception:
        red_health = None

    # listes pour les selects (Choices.js)
    try:
        choices_groups = sorted([k.decode() for k in red_groups.keys()])  # type: ignore[union-attr]
    except Exception:
        choices_groups = []
    try:
        choices_markets = sorted([k.decode() for k in red_markets.keys()])  # type: ignore[union-attr]
    except Exception:
        choices_markets = []

    def load_entry(_kind: str, name: str) -> tuple[Any, Any]:
        if not name:
            return None, None
        db = red_groups if _kind == "group" else red_markets
        key = None
        for k in db.keys():  # type: ignore[union-attr]
            kd = k.decode()
            if kd.lower() == name.lower():
                key = k
                break
        if not key:
            return None, None
        try:
            entry = json.loads(db.get(key))  # type: ignore[arg-type]
        except Exception:
            entry = None
        if entry is not None and "name" not in entry:
            entry["name"] = key.decode()
        return key, entry

    def posts_in_window(key: Any, days: int) -> int:
        posts = []
        if key and key in red_posts.keys():  # type: ignore[operator]
            try:
                posts = json.loads(red_posts.get(key))  # type: ignore[arg-type]
            except Exception:
                posts = []
        now = dt.now()
        cutoff = now - timedelta(days=days)
        c = 0
        for p in posts:
            ts = p.get("discovered") or p.get("timestamp") or p.get("time")
            d = None
            if isinstance(ts, str):
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        d = dt.strptime(ts, fmt)
                        break
                    except Exception:
                        pass
            if d is None and ts:
                try:
                    d = parser.parse(ts)
                except Exception:
                    d = None
            if d and d > cutoff:
                c += 1
        return c

    def avg_uptime30(entry_name: str, locations: list[Any]) -> int | None:
        if not red_health:
            return None
        vals = []
        for loc in locations:
            try:
                slug = (loc.get("slug") or "").strip()
                if not slug:
                    continue
                raw = red_health.get(f"health:{entry_name}:{slug}")
                if not raw:
                    continue
                series = json.loads(raw)  # type: ignore[arg-type]
                if not isinstance(series, list) or not series:
                    continue
                last = series[-30:]
                norm = [1 if (x in (1, True, "1", "up", "active")) else 0 for x in last]
                if norm:
                    vals.append(sum(norm) / len(norm))
            except Exception:
                continue
        return round(100 * sum(vals) / len(vals)) if vals else None

    def compute(_kind: str, name: str) -> dict[str, Any] | None:
        key, entry = load_entry(_kind, name)
        if not entry:
            return None
        locs = entry.get("locations", []) or []
        if not current_user.is_authenticated:
            locs = [l for l in locs if not l.get("private")]
        # pour coller aux DLS, on affiche les “URLs principales”
        visible = [l for l in locs if not l.get("fs") and not l.get("chat") and not l.get("admin")] or locs
        total = len(visible)
        up = sum(1 for l in visible if l.get("available") in (True, 1, "1"))
        return {
            "name": entry.get("name", name),
            "posts7": posts_in_window(key, 7),
            "posts30": posts_in_window(key, 30),
            "posts365": posts_in_window(key, 365),
            "mirrors_total": total,
            "mirrors_up": up,
            "captcha": entry.get("captcha", False),
            "raas": entry.get("raas", False),
            "uptime30": avg_uptime30(entry.get("name", name), visible),
        }

    a = compute(kind, name_a) if name_a else None
    b = compute(kind, name_b) if name_b else None
    error = None
    if (name_a or name_b) and (not a or not b):
        error = "Entrée introuvable (vérifie les sélections)."

    return render_template(
        "compare.html",
        kind=kind,
        a=a,
        b=b,
        error=error,
        choices_groups=choices_groups,
        choices_markets=choices_markets,
        sel_a=name_a,
        sel_b=name_b,
    )


# Note: /api/notes/<note_id> is now served by NotesAPI namespace (see api/notesapi.py)


# === RL backlink helpers (auto-injected) ===
def _rl_norm_key(s: str) -> str:
    return (s or "").strip().lower()


def _rl_lines(text: str) -> list[str]:
    return [l.strip() for l in (text or "").replace("\r", "").split("\n") if l.strip()]


def _rl_resolve_key_ci(red: Valkey, key_lower: str) -> Any:
    for kk in red.keys():  # type: ignore[union-attr]
        if kk.decode().lower() == key_lower:
            return kk
    return None


def _rl_load_json(red: Valkey, k: Any) -> Any:
    try:
        raw = red.get(k)
        return json.loads(raw) if raw else None  # type: ignore[arg-type]
    except Exception:
        return None


def _rl_save_json(red: Valkey, k: Any, obj: dict[str, Any]) -> None:
    red.set(k, json.dumps(obj, ensure_ascii=False))


def _rl_update_actor_relation(actor_lower: str, rel_key: str, value: str, present: bool) -> None:
    """Update actor's relations[rel_key] with value (add/remove), if actor exists in db=5."""
    red_a = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    rk = _rl_resolve_key_ci(red_a, actor_lower)
    if not rk:
        return
    obj = _rl_load_json(red_a, rk) or {}
    rel = obj.get("relations") or {}
    arr = rel.get(rel_key) or []
    lower_set = [str(x).lower() for x in arr]
    changed = False
    if present:
        if value.lower() not in lower_set:
            arr.append(value)
            changed = True
    else:
        new_arr = [x for x in arr if str(x).lower() != value.lower()]
        if len(new_arr) != len(arr):
            arr = new_arr
            changed = True
    if changed:
        rel[rel_key] = arr
        obj["relations"] = rel
        obj["updated_at"] = dt.utcnow().isoformat() + "Z"
        _rl_save_json(red_a, rk, obj)


def _rl_rename_in_all_actors(rel_key: str, old_value: str, new_value: str) -> None:
    """Replace old_value -> new_value (case-insensitive) inside relations[rel_key] for all actors (db=5)."""
    red_a = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    old_l = (old_value or "").lower()
    for rk in red_a.keys():  # type: ignore[union-attr]
        try:
            obj = json.loads(red_a.get(rk)) or {}  # type: ignore[arg-type]
        except Exception:
            continue
        rel = obj.get("relations") or {}
        arr = rel.get(rel_key) or []
        if not isinstance(arr, list):
            continue
        new_arr = [(new_value if str(x).lower() == old_l else x) for x in arr]
        if new_arr != arr:
            rel[rel_key] = new_arr
            obj["relations"] = rel
            obj["updated_at"] = dt.utcnow().isoformat() + "Z"
            red_a.set(rk, json.dumps(obj, ensure_ascii=False))


# === end RL helpers ===
