#!/usr/bin/env python3
"""Seed 10 threat actors into Redis DB=5 for testing."""

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from valkey import Valkey

from ransomlook.default import DB_ACTORS, get_socket_path

ACTORS: list[dict[str, Any]] = [
    {
        "name": "ShadowBroker77",
        "aliases": ["SB77", "Shadow77"],
        "private": False,
        "wanted": {"fbi": {"url": "https://www.fbi.gov/wanted/cyber/shadowbroker77"}, "europol": {}, "interpol": {}},
        "relations": {
            "groups": ["lockbit3", "Qilin"],
            "forums": [],
            "peers": [{"name": "DarkVortex"}, {"name": "CryptoGh0st"}],
        },
        "contacts": {"telegram": ["https://t.me/sb77_official"], "x": [], "email": ["sb77@proton.me"]},
        "profile": [],
    },
    {
        "name": "DarkVortex",
        "aliases": ["DVortex", "D4rkV0rt3x"],
        "private": False,
        "wanted": {"fbi": {}, "europol": {"url": "https://www.europol.europa.eu/wanted/darkvortex"}, "interpol": {}},
        "relations": {
            "groups": ["Akira", "lockbit5"],
            "forums": [],
            "peers": [{"name": "ShadowBroker77"}, {"name": "NightCrawler"}],
        },
        "contacts": {"telegram": [], "x": ["https://x.com/darkvortex_ops"], "email": ["dvortex@tutanota.com"]},
        "profile": [],
    },
    {
        "name": "CryptoGh0st",
        "aliases": ["CG0", "Gh0stCrypt"],
        "private": False,
        "wanted": {
            "fbi": {},
            "europol": {},
            "interpol": {"url": "https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices/cryptogh0st"},
        },
        "relations": {"groups": ["Qilin"], "forums": [], "peers": [{"name": "ShadowBroker77"}]},
        "contacts": {"telegram": ["https://t.me/cryptogh0st"], "email": []},
        "profile": [],
    },
    {
        "name": "NightCrawler",
        "aliases": ["NC_ops", "Crawler"],
        "private": False,
        "wanted": {"fbi": {}, "europol": {}, "interpol": {}},
        "relations": {
            "groups": ["lockbit3", "lockbit5"],
            "forums": [],
            "peers": [{"name": "DarkVortex"}, {"name": "Ph4ntom"}],
        },
        "contacts": {"x": ["https://x.com/nightcrawler_rw"], "email": ["nc@onionmail.org"]},
        "profile": [],
    },
    {
        "name": "Ph4ntom",
        "aliases": ["Phantom", "Phant0m_X"],
        "private": False,
        "wanted": {
            "fbi": {"url": "https://www.fbi.gov/wanted/cyber/ph4ntom"},
            "europol": {"url": "https://www.europol.europa.eu/wanted/ph4ntom"},
            "interpol": {},
        },
        "relations": {
            "groups": ["Akira", "Qilin"],
            "forums": [],
            "peers": [{"name": "NightCrawler"}, {"name": "ZeroDay_King"}],
        },
        "contacts": {"telegram": ["https://t.me/ph4ntom_ops"], "email": ["phantom@dnmx.org"]},
        "profile": [],
    },
    {
        "name": "ZeroDay_King",
        "aliases": ["ZDK", "0dayKing"],
        "private": False,
        "wanted": {"fbi": {}, "europol": {}, "interpol": {}},
        "relations": {"groups": ["lockbit5"], "forums": [], "peers": [{"name": "Ph4ntom"}]},
        "contacts": {"telegram": [], "email": ["zdk@cock.li"]},
        "profile": [],
    },
    {
        "name": "RansomQueen",
        "aliases": ["RQ", "QueenOfRansom"],
        "private": False,
        "wanted": {"fbi": {}, "europol": {}, "interpol": {}},
        "relations": {
            "groups": ["Qilin", "Akira"],
            "forums": [],
            "peers": [{"name": "CryptoGh0st"}, {"name": "ShadowBroker77"}],
        },
        "contacts": {"telegram": ["https://t.me/ransomqueen"], "x": ["https://x.com/ransomqueen_rw"], "email": []},
        "profile": [],
    },
    {
        "name": "IceBreaker",
        "aliases": ["IceB", "Br3aker"],
        "private": False,
        "wanted": {"fbi": {}, "europol": {}, "interpol": {}},
        "relations": {"groups": ["lockbit3"], "forums": [], "peers": [{"name": "NightCrawler"}]},
        "contacts": {"email": ["icebreaker@proton.me"]},
        "profile": [],
    },
    {
        "name": "BlackManta",
        "aliases": ["BM_ops", "Manta"],
        "private": False,
        "wanted": {
            "fbi": {"url": "https://www.fbi.gov/wanted/cyber/blackmanta"},
            "europol": {},
            "interpol": {"url": "https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices/blackmanta"},
        },
        "relations": {
            "groups": ["Akira", "lockbit5", "Qilin"],
            "forums": [],
            "peers": [{"name": "DarkVortex"}, {"name": "Ph4ntom"}, {"name": "RansomQueen"}],
        },
        "contacts": {
            "telegram": ["https://t.me/blackmanta_rw"],
            "x": ["https://x.com/blackmanta_ops"],
            "email": ["bmanta@dnmx.org"],
        },
        "profile": [],
    },
    {
        "name": "SilentReaper",
        "aliases": ["SR", "Reaper_Silent"],
        "private": True,
        "wanted": {"fbi": {}, "europol": {}, "interpol": {}},
        "relations": {"groups": ["lockbit3"], "forums": [], "peers": [{"name": "IceBreaker"}]},
        "contacts": {"email": ["silentreaper@onionmail.org"]},
        "profile": [],
    },
]


def main() -> None:
    red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_ACTORS)
    for actor in ACTORS:
        name = actor["name"]
        red.set(name, json.dumps(actor, ensure_ascii=False))
        flag = "🔒" if actor.get("private") else "✓"
        groups = ", ".join(actor.get("relations", {}).get("groups", []))
        print(f"  {flag} {name:20s}  groups=[{groups}]")
    print(f"\n{len(ACTORS)} actors seeded into DB=5")


if __name__ == "__main__":
    main()
