"""
Parser for the "Puppeteer" leak site (group: puppeteer).

Hash-routed SPA filled from the public JSON endpoint /api/posts ->
{"posts": [{id, client, name, description, isPublic, ...}]}.

Capture the /api/posts body into source/puppeteer-*. The browser renders JSON
inside a <pre> tag, so the saved file is HTML wrapping the JSON. Each victim's
detail is opened client-side by its id, so the screenshot link is /#/<id>.
"""

import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    list_div: list[dict[str, str]] = []
    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        try:
            with open(os.path.join("source", filename), encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
            pre = soup.find("pre")
            text = pre.get_text() if pre else soup.get_text()
            if not text.lstrip().startswith(("{", "[")):
                continue  # not the /api/posts capture (e.g. the SPA shell)
            data = json.loads(text)
            for post in data.get("posts", []):
                if post.get("isPublic") is False:
                    continue
                title = (post.get("name") or post.get("client") or "").strip()
                if not title:
                    continue
                description = " ".join((post.get("description") or "").split())
                if description.lower().startswith("no description given"):
                    description = ""
                list_div.append({
                    "title": title,
                    "description": description,
                    "link": "/#/" + post["id"],
                    "slug": filename,
                })
        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)
    logger.debug(list_div)
    return list_div
