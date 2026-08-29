import os
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []
    seen: set[str] = set()

    for filename in sorted(os.listdir("source")):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

            for row in soup.select("table.landing tr"):
                anchor = row.select_one("a")
                if not anchor:
                    continue
                title = " ".join(anchor.text.split())
                if not title or title in seen:
                    continue
                seen.add(title)

                parts = []
                for cell, label in (("size", "size"), ("mode", "status"), ("when", "hosting")):
                    found = row.select_one("td." + cell)
                    if found and found.text.strip():
                        parts.append(f"{label}: {' '.join(found.text.split())}")

                entry = {"title": title, "description": " | ".join(parts), "slug": filename}
                path = urlsplit(str(anchor.get("href") or "")).path
                if path and path != "/":
                    entry["link"] = path
                list_div.append(entry)
        except Exception:
            logger.debug("Failed during : " + filename)

    logger.debug(list_div)
    return list_div
