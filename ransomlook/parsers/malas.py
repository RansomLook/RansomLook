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
                if filename.endswith("xml.html"):
                    items = soup.find_all("item")
                    for item in items:
                        title = item.title.text
                        description = item.description.text
                        list_div.append({"title": title, "description": description})
                else:
                    liste = soup.find("ul", {"class": "list"})
                    divs_name = liste.find_all("li")  # type: ignore
                    for div in divs_name:
                        title = div.a["title"].strip()
                        description = ""
                        link = div.a["href"]
                        list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
