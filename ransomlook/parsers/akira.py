import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []
    for filename in os.listdir("source"):
        if filename.startswith(__name__.split(".")[-1] + "-"):
            html_doc = "source/" + filename
            file = open(html_doc, encoding="utf-8")
            soup = BeautifulSoup(file, "html.parser")
            if "onion-n" in filename:
                jsonpart = soup.pre.contents  # type: ignore
                data = json.loads(jsonpart[0])  # type: ignore
                for entry in data["objects"]:
                    title = entry["title"].replace("\n", "").strip()
                    description = entry["content"].replace("\n", "").strip()
                    list_div.append({"title": title, "description": description})
            file.close()
    logger.debug(list_div)
    return list_div
