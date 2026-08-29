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

            for item in soup.select("article.leek-item"):
                heading = item.select_one("h2.leek-title")
                if not heading:
                    continue
                title = " ".join(heading.text.split())
                if not title or title in seen:
                    continue
                seen.add(title)

                hosts = []
                local = False
                for link in item.select("a.mirror"):
                    href = str(link.get("href") or "")
                    host = urlsplit(href).netloc
                    if host:
                        if host not in hosts:
                            hosts.append(host)
                    elif href:
                        local = True
                if item.select_one("video source"):
                    local = True

                parts = []
                if local:
                    parts.append("hosted on the site")
                if hosts:
                    parts.append("mirrors: " + ", ".join(hosts))
                list_div.append({"title": title, "description": " | ".join(parts), "slug": filename})
        except Exception:
            logger.debug("Failed during : " + filename)

    logger.debug(list_div)
    return list_div
