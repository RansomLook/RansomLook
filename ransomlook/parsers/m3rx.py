import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []
    for filename in os.listdir("source"):
        if filename.startswith(__name__.split(".")[-1] + "-") and "cards.json" in filename:
            html_doc = "source/" + filename
            file = open(html_doc, encoding="utf-8")
            soup = BeautifulSoup(file, "html.parser")
            jsonpart = soup.pre.contents  # type: ignore
            data = json.loads(jsonpart[0])  # type: ignore
            for entry in data:
                title = entry["title"].replace("\n", "").strip()
                description = entry["text"].replace("\n", "").strip()
                stolen = entry.get("stolen", "").replace("\n", "").strip()
                if stolen:
                    description = description + " Stolen: " + stolen
                list_div.append({"title": title, "description": description})
            file.close()
    logger.debug(list_div)
    return list_div
