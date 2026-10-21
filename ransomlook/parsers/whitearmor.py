import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                data = json.loads(soup.pre.text)  # type: ignore
                for entry in data["publications"]:
                    title = entry["title"].strip()
                    description = (entry.get("body") or "").strip()
                    if entry.get("slug"):
                        link = "/post/" + entry["slug"]
                    else:
                        link = "/post?id=" + str(entry["id"])
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
