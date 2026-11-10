import json
import os
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def _describe(rec: dict[str, Any]) -> str:
    parts = []
    if rec.get("country"):
        parts.append(f"Country: {rec['country']}")
    if rec.get("employees"):
        parts.append(f"Employees: {rec['employees']}")
    if rec.get("revenue"):
        parts.append(f"Revenue: ${rec['revenue']:,}" if isinstance(rec["revenue"], int) else f"Revenue: {rec['revenue']}")
    if rec.get("dataWeight"):
        parts.append(f"Data: {rec['dataWeight']} {rec.get('dataWeightUnit') or ''}".strip())
    info = [t for t in rec.get("infoType") or [] if t]
    if info:
        parts.append("Type: " + ", ".join(info))
    if rec.get("dataPublishAt"):
        parts.append(f"Data publication: {str(rec['dataPublishAt'])[:10]}")
    if rec.get("dataPublished"):
        parts.append("Data published")
    if rec.get("status"):
        parts.append(f"Status: {rec['status']}")
    about = str(rec.get("about") or "").strip()
    head = " | ".join(parts)
    return f"{head}\n{about}" if head and about else head or about


def main() -> list[dict[str, str]]:
    """
    Parser for the AOQIN Leaks DLS (React SPA, single page, no per-victim route).

    The init_script copies the SPA's public clients JSON into
    <script type="application/json" id="rl-aoqin-clients">; fall back to the
    rendered list (div.pub-list-item > div.pub-list-name) if it is missing.

    Screenshots: link is '#CompanyName' — the init_script clicks the matching
    list item so the detail panel is rendered.
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            records: list[dict[str, Any]] = []
            blob = soup.find("script", id="rl-aoqin-clients")
            if blob and blob.string:
                try:
                    data = json.loads(blob.string)
                    if isinstance(data, list):
                        records = [r for r in data if isinstance(r, dict)]
                except ValueError as e:
                    logger.error("Bad clients JSON in %s: %s", filename, e)

            if records:
                for rec in records:
                    title = str(rec.get("companyName") or "").strip()
                    if title:
                        list_div.append(
                            {"title": title, "description": _describe(rec), "link": "#" + quote(title), "slug": filename}
                        )
                continue

            for item in soup.find_all("div", class_="pub-list-item"):
                name = item.find("div", class_="pub-list-name")
                title = name.get_text(strip=True) if name else ""
                if title:
                    list_div.append({"title": title, "description": "", "link": "#" + quote(title), "slug": filename})

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
