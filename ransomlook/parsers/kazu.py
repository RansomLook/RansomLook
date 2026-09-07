import json
import os
import re

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

# The victim cards live in a JS array literal: `const platforms` since the site
# split into /ransom.html and /databases.html, `const companies` before that.
ARRAY = re.compile(r"const\s+(?:platforms|companies)\s*=\s*\[")
# Every field we care about is a double-quoted string; `id` is a bare number
# and is skipped, which is fine.
FIELD = re.compile(r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*")')

FACTS = (("ransom", "Ransom"), ("price", "Price"), ("size", "Size"),
         ("record", "Records"), ("expires", "Expires"), ("dumpDate", "Dump date"))


def cards(raw: str) -> list[dict[str, str]]:
    """Fields of every card in the array, without parsing JavaScript.

    A key that shows up twice means the previous card ended, which is enough to
    split them: no need to balance braces or quote keys.
    """
    match = ARRAY.search(raw)
    if not match:
        return []
    block = raw[match.end(): raw.find("];", match.end())]
    out: list[dict[str, str]] = []
    card: dict[str, str] = {}
    for key, value in FIELD.findall(block):
        if key in card:
            out.append(card)
            card = {}
        try:
            card[key] = json.loads(value)
        except ValueError:
            continue
    if card:
        out.append(card)
    return out


def describe(card: dict[str, str]) -> str:
    """Description plus the sale/ransom facts printed on the card."""
    text = card.get("description", "").strip()
    facts = [f"{label}: {card[key].strip()}" for key, label in FACTS if card.get(key, "").strip()]
    if facts:
        text = (text + "\n\n" if text else "") + " | ".join(facts)
    return text


def main() -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}

    for filename in sorted(os.listdir("source")):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8", errors="replace") as file:
                found = cards(file.read())
        except Exception:
            logger.debug("Failed during : " + filename)
            continue
        for card in found:
            # `title` since the redesign, `name` on the old layout.
            title = (card.get("title") or card.get("name") or "").strip()
            if not title:
                continue
            # No link: a card opens a modal, and its `link` field points at the
            # victim's own site, which must never become a capture target.
            entries[title] = {"title": title, "description": describe(card), "slug": filename}

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
