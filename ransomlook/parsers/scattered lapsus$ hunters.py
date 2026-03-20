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
                divs_name = soup.find_all("div", {"class": "Magi-kard"})
                for div in divs_name:
                    title = div.find("div", {"class": "vting-name"}).text.strip()
                    description = ""
                    if div.has_attr("onclick"):
                        link = div["onclick"].split("'")[1]
                        if link == "f8ebf597d1193b645ec3e6493f24f6cb":
                            link = "toyota.html"
                        list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                    else:
                        list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
