import hashlib
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import flask_login  # type: ignore
from valkey import Valkey
from werkzeug.security import generate_password_hash

from ransomlook.default import DB_TASKS, get_config, get_homedir, get_socket_path


def load_user_from_request(request):  # type: ignore
    api_key = request.headers.get("Authorization")
    if not api_key:
        return None
    user = User()
    api_key = api_key.strip()
    keys_table = build_keys_table()
    if api_key in keys_table:
        user.id = keys_table[api_key]
        return user
    return None


class User(flask_login.UserMixin):  # type: ignore
    pass


@lru_cache(64)
def build_keys_table() -> dict[str, str]:
    keys_table = {}
    for username, authstuff in build_users_table().items():
        if "authkey" in authstuff:
            keys_table[authstuff["authkey"]] = username
    return keys_table


@lru_cache(64)
def get_users() -> Any:
    try:
        # Use legacy user mgmt, no need to print a warning, and it will fail on new install.
        return get_config("generic", "cache_clean_user", quiet=True)
    except Exception:
        return get_config("generic", "users")


@lru_cache(64)
def build_users_table() -> dict[str, dict[str, str]]:
    users_table: dict[str, dict[str, str]] = {}
    for username, authstuff in get_users().items():
        if isinstance(authstuff, str):
            # just a password, make a key
            users_table[username] = {}
            users_table[username]["password"] = generate_password_hash(authstuff)
            users_table[username]["authkey"] = hashlib.pbkdf2_hmac(
                "sha256", get_secret_key(), authstuff.encode(), 100000
            ).hex()

        elif isinstance(authstuff, list) and len(authstuff) == 2:
            if isinstance(authstuff[0], str) and isinstance(authstuff[1], str) and len(authstuff[1]) == 64:
                users_table[username] = {}
                users_table[username]["password"] = generate_password_hash(authstuff[0])
                users_table[username]["authkey"] = authstuff[1]
        else:
            raise Exception(
                'User setup invalid. Must be "username": "password" or "username": ["password", "token 64 chars (sha256)"]'
            )
    return users_table


@lru_cache(64)
def get_secret_key() -> bytes:
    secret_file_path: Path = get_homedir() / "secret_key"
    if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
        if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
            with secret_file_path.open("wb") as f:
                f.write(os.urandom(64))
    with secret_file_path.open("rb") as f:
        return f.read()


@lru_cache(64)
def sri_load() -> Any:
    with (get_homedir() / "website" / "web" / "sri.txt").open() as f:
        return json.load(f)


def api_key_meta(request: Any) -> dict[str, Any] | None:
    """Resolve the Redis API key carried by the Authorization header.

    Returns the key's meta dict when it exists and is active, None otherwise.
    Refreshes `last_used` as a side effect, so every authenticated call is
    accounted for and not just the exports.
    """
    token = (request.headers.get("Authorization") or "").strip()
    if not token:
        return None
    try:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)
        raw = red.hget("apikeys", token)
    except Exception:
        return None
    if not raw:
        return None
    try:
        meta = json.loads(raw)  # type: ignore[arg-type]
    except Exception:
        return None
    if not meta.get("active", True):
        return None
    try:
        meta["last_used"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        red.hset("apikeys", token, json.dumps(meta, ensure_ascii=False))
    except Exception:
        pass
    return meta


def viewer_is_authenticated(request: Any = None) -> bool:
    """True when the caller is a known principal: an admin session, a legacy
    generic.json key, or any active Redis API key."""
    req = _request(request)
    try:
        if flask_login.current_user.is_authenticated:
            return True
    except Exception:
        pass
    try:
        if load_user_from_request(req):  # type: ignore[no-untyped-call]
            return True
    except Exception:
        pass
    return api_key_meta(req) is not None


def viewer_can_see_private(request: Any = None) -> bool:
    """True when the caller may see entries flagged private.

    An admin session and a legacy generic.json key both map to a real user, so
    they see everything. A Redis API key only does when its meta carries
    `private: true` — keys issued before this existed keep their old, narrower
    view rather than silently gaining access to private data.
    """
    req = _request(request)
    try:
        if flask_login.current_user.is_authenticated:
            return True
    except Exception:
        pass
    try:
        if load_user_from_request(req):  # type: ignore[no-untyped-call]
            return True
    except Exception:
        pass
    meta = api_key_meta(req)
    return bool(meta and meta.get("private") is True)


def _request(request: Any) -> Any:
    """Fall back to the ambient Flask request when none is passed in."""
    if request is not None:
        return request
    from flask import request as flask_request

    return flask_request
