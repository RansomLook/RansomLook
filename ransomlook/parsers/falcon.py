import os
import re

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def main() -> list[dict[str, str]]:
    captures = []
    for filename in sorted(os.listdir("source")):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                captures.append((filename, BeautifulSoup(file, "html.parser")))
        except Exception:
            logger.debug("Failed during : " + filename)

    list_div = []
    seen: set[str] = set()

    for filename, soup in captures:
        try:
            for row in soup.select("table.data-table tbody tr"):
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                title = cells[0].text.strip()
                if not title or key(title) in seen:
                    continue
                description = "{} — {} compressed, {} uncompressed".format(
                    cells[1].text.strip(), cells[3].text.strip(), cells[4].text.strip()
                )
                seen.add(key(title))
                list_div.append({"title": title, "description": description, "slug": filename})
        except Exception:
            logger.debug("Failed during : " + filename)

    for filename, soup in captures:
        try:
            for item in soup.select("ul.entity-list li"):
                name = item.find("a", {"class": "entity-name"})
                if not name:
                    continue
                title = name.text.strip()
                if not title or any(key(title) in s or s in key(title) for s in seen):
                    continue
                meta = item.find("span", {"class": "entity-meta"})
                seen.add(key(title))
                list_div.append(
                    {
                        "title": title,
                        "description": meta.text.strip() if meta else "",
                        "slug": filename,
                    }
                )
        except Exception:
            logger.debug("Failed during : " + filename)

    logger.debug(list_div)
    return list_div
