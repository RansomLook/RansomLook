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
            divs_name = soup.find_all("div", {"data-slot": "card"})
            for div in divs_name:
                title = div.find("h3").text.strip()
                description = ""
                try:
                    link = div.find("a")["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})

                except Exception:
                    list_div.append({"title": title, "description": description})
            file.close()
    logger.debug(list_div)
    return list_div
