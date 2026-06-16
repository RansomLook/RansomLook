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
            divs_name = soup.find_all("t_8")
            for div in divs_name:
                title = div.find("t_10").text.strip()
                description = div.find("t_12").text.strip()
                list_div.append({"title": title, "description": description})
            file.close()
    logger.debug(list_div)
    return list_div
