import os
import re

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
                for div in soup.find_all("div", {"data-testid": re.compile(r"^mesa-recipe-[0-9a-f]+$")}):
                    title = div.find("strong").text.strip()
                    description = div.find("div", {"class": "min-w-0"}).text.strip()
                    link = "/breaches#" + div["data-testid"].removeprefix("mesa-recipe-")
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
