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
            divs_name = soup.find_all("div", {"class": "wrapper ng-star-inserted"})
            for div in divs_name:
                try:
                    title = div.find("div", {"class": "title"}).text.strip()
                    description = ""
                    link = div.a["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                except Exception:
                    pass
            divs_name = soup.find_all("div", {"class": "wrapper ng-star-inserted selected"})
            for div in divs_name:
                try:
                    title = div.find("div", {"class": "title"}).text.strip()
                    description = ""
                    link = div.a["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                except Exception:
                    pass
            file.close()
    logger.debug(list_div)
    return list_div
