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
                if "-api" in filename:
                    pre = soup.find("pre")
                    json_text = pre.get_text()  # type: ignore
                    data = json.loads(json_text)

                    for entry in data.get("data", {}).get("companies", []):
                        title = entry.get("name", "")
                        description = entry.get("description", "")
                        list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
