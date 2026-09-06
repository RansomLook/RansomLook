import json
import os

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        with open("source/" + filename, encoding="utf-8") as file:
            soup = BeautifulSoup(file, "html.parser")

        descriptions = {}
        blob = soup.find("script", id="rl-blacklocks-data")
        if isinstance(blob, Tag) and blob.string:
            try:
                for record in json.loads(blob.string):
                    descriptions[record["title"]] = record.get("description", "")
            except Exception:
                logger.debug("Failed blob in : " + filename)

        for item in soup.find_all("a", class_="sidebar-item"):
            try:
                title = item.find("span").text.strip()
                link = item["href"]
                list_div.append(
                    {
                        "title": title,
                        "description": descriptions.get(title, ""),
                        # Keep the path: the host is prepended later, so a mirror
                        # rotation must not pin the post to the onion scraped today.
                        "link": link[link.find("/leaks/"):],
                        "slug": filename,
                    }
                )
            except Exception:
                logger.debug("Failed entry in : " + filename)

    logger.debug(list_div)
    return list_div
