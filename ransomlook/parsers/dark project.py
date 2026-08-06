import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "http://darkprn3d3udnhpuxknsrhft3376lrz5tenhgkrxge5hxqe46pkbrwid.onion"


def main() -> list[dict[str, str]]:
    """
    Dark Project serves its victim list as plain JSON at /api/v1/posts
    ({"items": [...]}, no server-rendered HTML). The saved source file is
    either the raw JSON body or that JSON wrapped in a <pre> tag by the browser.
    """
    list_div = []

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

            for entry in data.get("items", []):
                title = str(entry.get("title") or "").strip()
                if not title:
                    continue
                description = str(entry.get("excerpt") or "").strip()
                slug = str(entry.get("slug") or "").strip()
                link = f"{BASE_URL}/article?slug={slug}" if slug else BASE_URL
                list_div.append({"title": title, "description": description, "link": link, "slug": filename})
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
