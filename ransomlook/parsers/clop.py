import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []
    blacklist = ["HOME", "HOW TO DOWNLOAD?", "ARCHIVE"]
    for filename in os.listdir("source"):
        if filename.startswith(__name__.split(".")[-1] + "-"):
            html_doc = "source/" + filename
            logger.debug(filename)
            file = open(html_doc, encoding="utf-8")
            soup = BeautifulSoup(file, "html.parser")
            divs_name = soup.find_all("span", {"class": "g-menu-item-title"})
            for div in divs_name:
                for item in div.contents:
                    if item in blacklist:
                        continue
                    list_div.append(item.text.strip())
            file.close()
    logger.debug(list_div)
    list_div = list(dict.fromkeys(list_div))
    return list_div
