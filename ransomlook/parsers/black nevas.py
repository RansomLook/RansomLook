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
                if "-publication" not in filename:
                    divs_name = soup.find_all("div", {"class": "p-4"})
                    for div in divs_name:
                        try:
                            title = div.find("h2").text.strip()
                            description = div.find("p").text.strip()
                            list_div.append({"title": title, "description": description})
                        except Exception:
                            continue
                else:
                    jsonpart = soup.pre.contents  # type: ignore
                    data = json.loads(jsonpart[0])  # type: ignore
                    for entry in data:
                        title = entry["company"].strip()
                        description = entry["description"].strip()
                        link = "/publications/details/" + entry["id"]
                        list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
