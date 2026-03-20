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
                try:
                    jsonpart = soup.pre.contents  # type: ignore
                    data = json.loads(jsonpart[0])  # type: ignore
                    for entry in data:
                        title = entry["name"]
                        description = entry["info"].strip()
                        list_div.append({"title": title, "description": description})
                except Exception:
                    pass
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
