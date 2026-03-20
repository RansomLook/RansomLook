#!/usr/bin/env python3
"""Seed Redis DB=1 'keywords' with sample alert keywords for testing."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from valkey import Valkey

from ransomlook.default import DB_TASKS, get_socket_path

red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS)

KEYWORDS = [
    # Companies / orgs
    "Airbus",
    "Boeing",
    "NVIDIA",
    "Samsung",
    "Microsoft",
    "Toyota",
    "Schneider Electric",
    "Thales",
    "Orange",
    "SFR",
    "EDF",
    "SNCF",
    "Carrefour",
    "BNP Paribas",
    "Société Générale",
    "AXA",
    "Allianz",
    "Deutsche Bank",
    "HSBC",
    "Barclays",
    # Governments / institutions
    "Ministry of Defense",
    "NATO",
    "European Commission",
    "FBI",
    "ANSSI",
    "NHS",
    "CISA",
    # Sectors
    "hospital",
    "school district",
    "municipality",
    "water utility",
    "power grid",
    "airport",
    "railway",
    # Infra / keywords
    "SCADA",
    "ICS",
    "critical infrastructure",
    "passport",
    "classified",
    "nuclear",
    "defense contractor",
    # Specific threat intel
    "lockbit",
    "blackcat",
    "alphv",
    "clop",
    "play",
    "8base",
    "medusa",
    "bianlian",
    "akira",
    "rhysida",
    "royal",
    "black basta",
    "vice society",
    "scattered spider",
    "lapsus",
]

red.set("keywords", "\n".join(KEYWORDS))

print(f"Inserted {len(KEYWORDS)} keywords into Redis DB=1 key 'keywords'.")
