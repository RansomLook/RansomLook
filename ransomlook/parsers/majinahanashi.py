import json
import os
from typing import Any

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]
BLOB_ID = "rl-majinahanashi-data"


def description(post: dict[str, Any]) -> str:
    parts = [str(post.get("lead") or post.get("summary") or "").strip(), str(post.get("body") or "").strip()]

    if post.get("status") == "scheduled" and post.get("releaseAt"):
        parts.append("Publication scheduled: " + str(post["releaseAt"]))

    package = post.get("package") or {}
    if package.get("sizeLabel"):
        parts.append(f"Package: {package['sizeLabel']} / {package.get('fileCount', '?')} files")
    if package.get("downloadUrl"):
        parts.append("File manager: " + str(package["downloadUrl"]))

    return "\n".join(part for part in parts if part)


def main() -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        try:
            with open(os.path.join("source", filename), encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

            blob = soup.find("script", id=BLOB_ID)
            if not isinstance(blob, Tag) or not blob.string:
                continue

            for post in json.loads(blob.string).get("posts", []):
                title = str(post.get("title") or "").strip()
                # source=news holds the group's announcements, not victims
                if not title or post.get("kind") == "news":
                    continue
                entries[title] = {
                    "title": title,
                    "description": description(post),
                    "link": str(post.get("link") or ""),
                    "slug": filename,
                }
        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
