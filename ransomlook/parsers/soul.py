import json
import os
from typing import Any

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def _describe(rec: dict[str, Any]) -> str:
    parts = []
    for key, label in (
        ("category", "Sector"),
        ("location", "Location"),
        ("employees", "Employees"),
        ("revenue", "Revenue"),
        ("website", "Website"),
    ):
        value = str(rec.get(key) or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    status = str(rec.get("status") or "").strip()
    deadline = str(rec.get("deadline") or "").strip()
    if status:
        parts.append(f"Status: {status}")
    if deadline:
        parts.append(f"Deadline: {deadline[:16].replace('T', ' ')} UTC")
    about = str(rec.get("description") or "").strip()
    head = " | ".join(parts)
    return f"{head}\n{about}" if head and about else head or about


def main() -> list[dict[str, str]]:
    """
    Parser for the Soul group site (clearnet, Next.js).

    Location to scrape: https://codice-ledger.io/api/organizations — a JSON
    list of {name, category, description, revenue, employees, location,
    website, logo, id, deadline, status?}. Browsers wrap a JSON response in
    <pre>; fall back to the raw text. No per-victim page exists, so no link.
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                content = f.read()

            holder = BeautifulSoup(content, "html.parser").find("pre")
            raw = holder.get_text() if holder else content
            try:
                data = json.loads(raw)
            except ValueError:
                logger.error("No JSON in %s", filename)
                continue
            if isinstance(data, dict):
                data = data.get("organizations") or data.get("data") or []
            if not isinstance(data, list):
                continue

            for rec in data:
                if not isinstance(rec, dict):
                    continue
                title = str(rec.get("name") or "").strip()
                if title:
                    list_div.append({"title": title, "description": _describe(rec), "slug": filename})

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
