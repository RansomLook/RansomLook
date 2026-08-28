#!/usr/bin/env python3
"""RaaS affiliate rules: the terms a ransomware-as-a-service program imposes on
its affiliates — forbidden targets, excluded countries, revenue split, proof
obligations.

One Valkey key per group (DB_RAAS), holding the list of blocks. A program
rewrites its rules over time, so a group carries several blocks; each is a
Markdown body with optional screenshots, an optional start date and an optional
public comment. Exactly one block per group may be flagged ``current``.

Visibility is inherited from the group: nothing here has its own private flag.
A block belonging to a private group or market is hidden from anonymous
viewers everywhere — page, index, API and image route alike.
"""
import html
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import valkey

from .default import DB_RAAS, get_socket_path
from .default.config import get_homedir
from .sharedutils import errlog, is_private_entity

# Screenshots live outside source/screenshots on purpose: that tree is served by
# routes that perform no privacy check at all, so anything dropped there would
# be readable for a private group.
ASSET_ROOT = ("source", "raas")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_ALLOWED_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def getdb() -> valkey.Valkey:
    return valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_RAAS)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm_group(name: Any) -> str:
    """The DB_RAAS key for a group: same convention as DB_POSTS."""
    return str(name or "").strip().lower()


def valid_started(value: Any) -> str:
    """Keep a start date only when it is a real YYYY-MM-DD, else drop it.

    The field is optional and free text in the form, so a typo must leave the
    block undated rather than produce a value the sort cannot order.
    """
    text = str(value or "").strip()
    if not _DATE_RE.match(text):
        return ""
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return ""
    return text


def render_source(text: Any) -> str:
    """Neutralise raw HTML before the Markdown pass.

    Analyses are written by our own analysts; these blocks are pasted from an
    affiliate panel, so the body is adversary-authored. Python-Markdown lets
    inline HTML through and the template renders the result with |safe, so the
    angle brackets are escaped here first. Markdown itself still works —
    headings, lists, tables, fenced code — only raw HTML goes inert.
    """
    return html.escape(str(text or ""), quote=False)


def asset_dir(group: Any) -> str | None:
    """Absolute image directory for a group, or None if the name escapes it."""
    candidate = norm_group(group)
    if not candidate or candidate in (".", "..") or set(candidate) & {"/", "\\", "\0"}:
        return None
    base = os.path.realpath(os.path.join(str(get_homedir()), *ASSET_ROOT))
    target = os.path.realpath(os.path.join(base, candidate))
    if os.path.dirname(target) != base:
        return None
    return target


def safe_asset(name: Any) -> str | None:
    """A stored image filename, refused if it could walk out of the directory."""
    candidate = str(name or "").strip()
    if not candidate or candidate in (".", "..") or set(candidate) & {"/", "\\", "\0"}:
        return None
    if not candidate.lower().endswith(_ALLOWED_IMAGE_EXT):
        return None
    return candidate


def load(group: Any, red: valkey.Valkey | None = None) -> list[dict[str, Any]]:
    """Every block of a group, unsorted and unfiltered."""
    key = norm_group(group)
    if not key:
        return []
    try:
        raw = (red or getdb()).get(key)
        if not raw:
            return []
        blocks = json.loads(raw)  # type: ignore[arg-type]
    except Exception:
        errlog("raas: can not read " + key)
        return []
    return [b for b in blocks if isinstance(b, dict)] if isinstance(blocks, list) else []


def save(group: Any, blocks: list[dict[str, Any]], red: valkey.Valkey | None = None) -> None:
    """Persist a group's blocks, dropping the key when none are left."""
    key = norm_group(group)
    if not key:
        return
    red = red or getdb()
    if blocks:
        red.set(key, json.dumps(blocks, ensure_ascii=False))
    else:
        red.delete(key)


def sort_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Current block first, then dated newest-first, then undated.

    The current block leads whatever its date: it may well have none, and the
    reader is looking for "what the rules are now" before the history.
    """
    current = [b for b in blocks if b.get("current") is True]
    rest = [b for b in blocks if b.get("current") is not True]
    dated = sorted(
        (b for b in rest if valid_started(b.get("started"))),
        key=lambda b: str(b.get("started")),
        reverse=True,
    )
    undated = sorted(rest, key=lambda b: str(b.get("created_at") or ""), reverse=True)
    undated = [b for b in undated if not valid_started(b.get("started"))]
    return current + dated + undated


def make_block(content: str, comment: str = "", started: str = "", current: bool = False, author: str = "admin") -> dict[str, Any]:
    stamp = now_iso()
    return {
        "id": uuid.uuid4().hex,
        "content": content or "",
        "comment": comment or "",
        "started": valid_started(started),
        "current": bool(current),
        "images": [],
        "created_at": stamp,
        "updated_at": stamp,
        "created_by": author,
    }


def find(blocks: list[dict[str, Any]], block_id: str) -> dict[str, Any] | None:
    if not _ID_RE.match(str(block_id or "")):
        return None
    return next((b for b in blocks if b.get("id") == block_id), None)


def set_current(blocks: list[dict[str, Any]], block_id: str) -> None:
    """Mark one block current and clear the flag on every other one.

    A group has a single set of rules in force, so the flag is exclusive; doing
    it here means the admin views cannot forget it.
    """
    for b in blocks:
        b["current"] = b.get("id") == block_id


def public_groups(red: valkey.Valkey | None = None) -> list[str]:
    """Group names holding at least one block, private entities excluded."""
    return groups(include_private=False, red=red)


def groups(include_private: bool = False, red: valkey.Valkey | None = None) -> list[str]:
    red = red or getdb()
    out = []
    try:
        for key in red.keys():  # type: ignore[union-attr]
            name = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
            if not include_private and is_private_entity(name):
                continue
            if load(name, red):
                out.append(name)
    except Exception:
        errlog("raas: can not list groups")
        return []
    return sorted(out, key=str.lower)


def visible(group: Any, include_private: bool = False, red: valkey.Valkey | None = None) -> list[dict[str, Any]]:
    """Sorted blocks of a group for a given viewer.

    Returns nothing at all for a private group unless the viewer may see it:
    the blocks carry no flag of their own, they follow the entity.
    """
    key = norm_group(group)
    if not key:
        return []
    if not include_private and is_private_entity(key):
        return []
    return sort_blocks(load(key, red))


def count(group: Any, red: valkey.Valkey | None = None) -> int:
    return len(load(group, red))


def latest_date(blocks: list[dict[str, Any]]) -> str:
    """Most recent start date among blocks, empty when none is dated."""
    dates = [valid_started(b.get("started")) for b in blocks]
    dates = [d for d in dates if d]
    return max(dates) if dates else ""
