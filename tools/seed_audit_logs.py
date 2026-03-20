#!/usr/bin/env python3
"""Seed Redis DB=1 sorted set 'audit' with sample entries for testing."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone

from valkey import Valkey

from ransomlook.default import DB_TASKS, get_socket_path

red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)

USERS = ["admin@ransomlook.io", "analyst@ransomlook.io", "john@ransomlook.io"]

# Base time: now UTC, entries spread over the last 30 days
now = datetime.now(timezone.utc)

ENTRIES = [
    # ── Groups ──
    {"user": USERS[0], "action": "add_group", "target": "lockbit", "details": "url=http://lockbit3olp7oetl.onion"},
    {"user": USERS[0], "action": "add_group", "target": "blackcat", "details": "url=http://alphvmmm27o3abo.onion"},
    {"user": USERS[1], "action": "modify_group", "target": "lockbit", "details": "meta, private, raas"},
    {"user": USERS[0], "action": "rename_group", "target": "lockbit", "details": "new_name=lockbit3"},
    {"user": USERS[2], "action": "add_group", "target": "clop", "details": "url=http://clop2kdz5htpm.onion"},
    {"user": USERS[1], "action": "delete_group", "target": "oldgroup", "details": ""},
    {"user": USERS[0], "action": "modify_group", "target": "blackcat", "details": "affiliates, meta"},
    {"user": USERS[2], "action": "add_group", "target": "play", "details": "url=http://play4ti4gpb.onion"},
    {"user": USERS[0], "action": "add_group", "target": "8base", "details": "url=http://8base9kl3.onion"},
    # ── Posts ──
    {"user": USERS[1], "action": "add_post", "target": "lockbit3", "details": "title=VictimCorp Inc."},
    {"user": USERS[1], "action": "add_post", "target": "blackcat", "details": "title=AcmeHealth Systems"},
    {"user": USERS[0], "action": "add_post", "target": "clop", "details": "title=MegaBank PLC"},
    {"user": USERS[2], "action": "edit_posts", "target": "lockbit3", "details": "deleted=OldVictim Ltd"},
    {"user": USERS[1], "action": "add_post", "target": "play", "details": "title=CityGov Municipal"},
    {
        "user": USERS[0],
        "action": "edit_posts",
        "target": "blackcat",
        "details": "added=NewTarget SA; deleted=Duplicate Inc",
    },
    # ── Logos ──
    {"user": USERS[0], "action": "upload_logo", "target": "lockbit3", "details": "file=lockbit3-logo.png"},
    {"user": USERS[1], "action": "upload_logo", "target": "blackcat", "details": "file=blackcat-v2.png"},
    {"user": USERS[0], "action": "delete_logo", "target": "oldgroup", "details": "file=oldgroup-banner.png"},
    # ── Actors ──
    {"user": USERS[2], "action": "add_actor", "target": "wazawaka", "details": ""},
    {"user": USERS[0], "action": "add_actor", "target": "bassterlord", "details": ""},
    {"user": USERS[1], "action": "edit_actor", "target": "wazawaka", "details": "aliases, contacts, relations"},
    {"user": USERS[0], "action": "edit_actor", "target": "bassterlord", "details": "bio, identity, wanted"},
    {"user": USERS[2], "action": "add_actor", "target": "uhodiransomwar", "details": ""},
    # ── Ransomnotes ──
    {"user": USERS[0], "action": "create_note", "target": "lockbit3", "details": "title=README.txt"},
    {"user": USERS[1], "action": "create_note", "target": "blackcat", "details": "title=RECOVER-FILES.txt"},
    {"user": USERS[0], "action": "update_note", "target": "lockbit3", "details": "id=abc123, changed=content, status"},
    {"user": USERS[2], "action": "delete_note", "target": "clop", "details": "title=old-note.txt, id=def456"},
    {"user": USERS[1], "action": "add_note_alias", "target": "lockbit3", "details": "alias=lockbit-3.0"},
    {"user": USERS[0], "action": "delete_note_alias", "target": "blackcat", "details": "alias=alphv"},
    # ── Crypto ──
    {
        "user": USERS[0],
        "action": "add_crypto_addr",
        "target": "lockbit3",
        "details": "chain=bitcoin, addr=bc1q42lja79elem0anu8q860g3v35cz",
    },
    {
        "user": USERS[1],
        "action": "add_crypto_addr",
        "target": "blackcat",
        "details": "chain=ethereum, addr=0x4a8b2c1d3e5f6a7b8c9d0e1f",
    },
    {
        "user": USERS[2],
        "action": "edit_crypto_addr",
        "target": "lockbit3",
        "details": "chain=bitcoin, addr=bc1q42lja79elem0anu8q860g3v35cz, changed=label, tx_count",
    },
    {
        "user": USERS[0],
        "action": "delete_crypto_addr",
        "target": "clop",
        "details": "chain=bitcoin, addr=1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    },
    {"user": USERS[1], "action": "set_crypto_alias", "target": "lbit", "details": "canon=lockbit3"},
    {"user": USERS[0], "action": "delete_crypto_alias", "target": "oldname", "details": ""},
    # ── Alerting ──
    {"user": USERS[0], "action": "update_keywords", "target": "alerting", "details": "added=lockbit, conti, blackcat"},
    {
        "user": USERS[2],
        "action": "update_keywords",
        "target": "alerting",
        "details": "added=play, 8base; removed=conti",
    },
]

# Spread entries backwards from now, ~6 hours apart
interval = timedelta(hours=6)
count = 0

for i, e in enumerate(ENTRIES):
    entry_time = now - (interval * (len(ENTRIES) - 1 - i))
    ts = entry_time.timestamp()
    e["ts"] = entry_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = json.dumps(e, ensure_ascii=False)
    red.zadd("audit", {payload: ts})
    count += 1

print(f"Inserted {count} audit entries into Redis DB=1 sorted set 'audit'.")
print(
    f"Time range: {(now - interval * (len(ENTRIES) - 1)).strftime('%Y-%m-%d %H:%M')} → {now.strftime('%Y-%m-%d %H:%M')} UTC"
)
print(f"Total entries in set: {red.zcard('audit')}")
