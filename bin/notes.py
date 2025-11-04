#!/usr/bin/env python3
"""
bin/notes.py — Simple Valkey-only importer for ransom notes
- Clones/updates the ThreatLabz repo (or uses an existing path)
- Creates/updates notes in Valkey using the new schema
- Idempotent via external_uid (repo+path) and checksum
- Respects local_override (manual edits are never overwritten)

ENV:
  NOTES_REPO_URL  (default: https://github.com/threatlabz/ransomware_notes)
  NOTES_REPO_PATH (default: /tmp/ransomware_notes)

Requires: redis (Valkey-compatible), git CLI available in PATH
"""

import os
import sys
import json
import redis
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from ransomlook.default.config import get_socket_path

DB_INDEX = 11
REPO_URL = os.environ.get("NOTES_REPO_URL", "https://github.com/threatlabz/ransomware_notes")
REPO_PATH = Path(os.environ.get("NOTES_REPO_PATH", "/tmp/ransomware_notes"))

# ---------------- helpers ----------------

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()

def detect_format(filename: str) -> str:
    fn = filename.lower()
    if fn.endswith((".htm", ".html")):
        return "html"
    if fn.endswith(".md"):
        return "md"
    if fn.endswith(".rtf"):
        return "rtf"
    return "txt"

def normalize_group(s: str) -> str:
    import re
    s = (s or "").strip().lower().replace(" ", "-").replace("_", "-")
    s = re.sub(r"[^a-z0-9\-]+", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s

# --------------- Valkey access ---------------

def rconn() -> redis.Redis:
    return redis.Redis(unix_socket_path=get_socket_path("cache"), db=DB_INDEX)


def resolve_group(r: redis.Redis, raw: str) -> str | None:
    slug = normalize_group(raw)
    if not slug:
        return None
    if r.sismember("groups:slugs", slug):
        return slug
    mapped = r.hget("alias:group", slug)
    if mapped:
        return mapped.decode("utf-8")
    return None


def save_note(r: redis.Redis, note: dict) -> None:
    note_id = note["id"]
    pipe = r.pipeline()
    pipe.set(f"note:{note_id}", json.dumps(note, ensure_ascii=False))
    # indexes
    try:
        updated_ts = int(datetime.fromisoformat(note["updated_at"]).timestamp())
    except Exception:
        updated_ts = int(datetime.now(timezone.utc).timestamp())
    pipe.zadd("idx:notes:updated", {note_id: updated_ts})
    pipe.sadd(f"idx:status:{note.get('status','active')}", note_id)
    pipe.sadd(f"idx:format:{note.get('format','txt')}", note_id)
    for src in note.get("sources", []):
        if src.get("kind") == "git":
            pipe.sadd(f"idx:source:git:{src['repo']}", note_id)
        elif src.get("kind") == "manual":
            pipe.sadd("idx:source:manual", note_id)
    for g in note.get("groups", []):
        pipe.sadd(f"idx:group:{g}:notes", note_id)
    pipe.execute()


def append_version(r: redis.Redis, note_id: str, payload: dict) -> None:
    payload = {**payload, "ts": now_iso()}
    r.xadd(f"stream:note:{note_id}:versions", payload)


def audit(r: redis.Redis, action: str, **kw) -> None:
    r.xadd("stream:audit:notes", {"action": action, **{k: str(v) for k, v in kw.items()}})

# --------------- git repo handling ---------------

def ensure_repo() -> str:
    """Clone or update the repo; return current commit hash."""
    if not REPO_PATH.exists():
        REPO_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Cloning {REPO_URL} → {REPO_PATH}")
        subprocess.run(["git", "clone", "--depth=1", REPO_URL, str(REPO_PATH)], check=True)
    else:
        print(f"Updating repo in {REPO_PATH}")
        subprocess.run(["git", "-C", str(REPO_PATH), "fetch", "--depth=1", "origin"], check=True)
        # reset to origin/HEAD for a clean, idempotent state
        subprocess.run(["git", "-C", str(REPO_PATH), "reset", "--hard", "origin/HEAD"], check=True)

    commit = subprocess.check_output(["git", "-C", str(REPO_PATH), "rev-parse", "HEAD"]).decode().strip()
    return commit

# --------------- importer core ---------------

def run_import() -> None:
    r = rconn()
    # lock (15 minutes)
    if not r.set("lock:notes:import", "1", nx=True, ex=900):
        print("Another import is running. Abort.")
        return

    try:
        commit = ensure_repo()
        root = REPO_PATH
        imported = 0
        updated = 0
        skipped = 0

        for folder in sorted(os.listdir(root)):
            if folder.startswith('.'):
                continue
            folder_path = root / folder
            if not folder_path.is_dir():
                continue

            group_slug = resolve_group(r, folder) or normalize_group(folder)

            for dirpath, _, filenames in os.walk(folder_path):
                for filename in filenames:
                    fpath = Path(dirpath) / filename
                    try:
                        raw = fpath.read_bytes()
                    except Exception:
                        skipped += 1
                        continue

                    content = raw.decode(errors="replace")
                    fmt = detect_format(filename)
                    rel = fpath.relative_to(root).as_posix()  # e.g. LockBit/README.txt
                    external_uid = sha1(f"{REPO_URL}:{rel}")
                    checksum = sha256_bytes(raw)

                    note_id_bytes = r.hget("map:note:by_external_uid", external_uid)
                    if note_id_bytes:
                        note_id = note_id_bytes.decode("utf-8")
                        raw_note = r.get(f"note:{note_id}")
                        if not raw_note:
                            # stale mapping; drop and treat as new
                            r.hdel("map:note:by_external_uid", external_uid)
                        else:
                            note = json.loads(raw_note)
                            # respect local override: do not overwrite content
                            if note.get("local_override"):
                                if note.get("checksum") != checksum:
                                    append_version(r, note_id, {
                                        "kind": "upstream", "checksum": checksum, "repo": REPO_URL, "path": rel, "commit": commit,
                                    })
                                    note["pending_upstream"] = True
                                    save_note(r, note)
                                skipped += 1
                                continue
                            # update when checksum differs
                            if note.get("checksum") != checksum:
                                note["content"] = content
                                note["checksum"] = checksum
                                note["format"] = fmt
                                note["updated_at"] = now_iso()
                                if group_slug and group_slug not in note.get("groups", []):
                                    note.setdefault("groups", []).append(group_slug)
                                append_version(r, note_id, {
                                    "kind": "upstream", "checksum": checksum, "repo": REPO_URL, "path": rel, "commit": commit,
                                })
                                save_note(r, note)
                                updated += 1
                            else:
                                skipped += 1
                            continue

                    # New note
                    note_id = uuid4().hex
                    groups = [group_slug] if group_slug else []
                    note = {
                        "id": note_id,
                        "title": filename,
                        "content": content,
                        "format": fmt,
                        "language": None,
                        "groups": groups,
                        "sources": [{
                            "kind": "git", "repo": REPO_URL, "path": rel, "commit": commit,
                        }],
                        "external_uids": [external_uid],
                        "checksum": checksum,
                        "status": "active",
                        "local_override": False,
                        "pending_upstream": False,
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                        "created_by": "importer",
                        "updated_by": "importer",
                    }
                    r.hset("map:note:by_external_uid", external_uid, note_id)
                    save_note(r, note)
                    append_version(r, note_id, {"kind": "upstream", "checksum": checksum, "repo": REPO_URL, "path": rel, "commit": commit})
                    audit(r, "create", note_id=note_id, source="git", path=rel)
                    imported += 1

        print(f"Import done. new={imported} updated={updated} skipped={skipped}")
    finally:
        r.delete("lock:notes:import")


def main():
    try:
        run_import()
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
