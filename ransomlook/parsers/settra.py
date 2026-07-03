import json
import os
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def _clean(text: str) -> str:
    """Flatten the markdown leak note into a single readable line."""
    text = re.sub(r"[#*_`>]", " ", text)
    return " ".join(text.split())


def _date(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def parse_json(content: str, filename: str) -> list[dict[str, str]]:
    """Parse the /api/publish JSON feed (bare list of victim objects)."""
    list_div: list[dict[str, str]] = []
    data = json.loads(content)
    if isinstance(data, dict):
        for key in ("data", "items", "results", "leaks", "publish"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        return list_div
    for entry in data:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("site") or entry.get("name") or "").strip()
        if not title:
            continue
        meta = []
        if entry.get("revenue"):
            meta.append("Revenue: " + str(entry["revenue"]))
        if entry.get("cap"):
            meta.append("Size: " + str(entry["cap"]))
        note = _clean(str(entry.get("content", "")))
        description = " | ".join(filter(None, [" ".join(meta), note])).strip(" |")
        link = ""
        uid = entry.get("uid") or entry.get("id")
        if uid:
            link = "/leaks/" + str(uid)
        item = {"title": title, "description": description, "link": link, "slug": filename}
        date = _date(str(entry.get("publishedAt") or entry.get("createdAt") or ""))
        if date:
            item["date"] = date
        list_div.append(item)
    return list_div


def parse_html(content: str, filename: str) -> list[dict[str, str]]:
    """Fallback for the rendered /leaks SPA page (JS-hydrated cards)."""
    list_div = []
    soup = BeautifulSoup(content, "html.parser")
    for anchor in soup.find_all("a", href=True):
        if not anchor["href"].startswith("/leaks/"):
            continue
        heading = anchor.find("h3")
        if not heading:
            continue
        title = heading.text.strip()
        if not title:
            continue
        paragraph = anchor.find("p")
        description = paragraph.text.strip() if paragraph else ""
        list_div.append(
            {"title": title, "description": description, "link": anchor["href"], "slug": filename}
        )
    return list_div


def main() -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                with open(html_doc, encoding="utf-8") as file:
                    content = file.read()

                # The API feed may sit raw or inside a <pre> wrapper when
                # rendered through a browser.
                json_text = content
                stripped = content.lstrip()
                if not stripped.startswith(("{", "[")):
                    pre = BeautifulSoup(content, "html.parser").find("pre")
                    json_text = pre.text if pre else ""

                parsed = []
                if json_text.lstrip().startswith(("{", "[")):
                    try:
                        parsed = parse_json(json_text, filename)
                    except Exception:
                        parsed = []
                if not parsed:
                    parsed = parse_html(content, filename)

                for entry in parsed:
                    # /leaks and /api/publish may both be captured; dedupe by
                    # title and keep the richer (JSON) record.
                    prev = entries.get(entry["title"])
                    if prev is None or len(entry["description"]) > len(prev["description"]):
                        entries[entry["title"]] = entry
        except Exception:
            logger.debug("Failed during : " + filename)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
