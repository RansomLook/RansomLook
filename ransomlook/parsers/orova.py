import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    """
    Orova serves its victim list as plain JSON at /api/companies?page=N&pageSize=30
    ({"data": [...], "total": N}, no server-rendered HTML). More than one page may
    be fetched (multiple source files), so entries are deduped by id.
    """
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                raw = file.read()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                soup = BeautifulSoup(raw, "html.parser")
                pre = soup.find("pre")
                data = json.loads(pre.text) if pre else {}

            for entry in data.get("data", []):
                cid = str(entry.get("id") or "")
                title = str(entry.get("name") or "").strip()
                if not cid or not title:
                    continue
                entries[cid] = {
                    "title": title,
                    "description": str(entry.get("description") or "").strip(),
                    "link": str(entry.get("downloadUrl") or "").strip(),
                    "slug": filename,
                }
        except Exception:
            logger.debug("Failed during : " + filename)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
