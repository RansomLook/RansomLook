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
                divs_name = soup.find_all("div", {"class": "col-md-6"})
                for div in divs_name:
                    sec = div.find("div", {"class": "blog-list--desc p-3 cnt"})
                    title = sec.find("h3").text.strip()
                    description = sec.find("p").text.strip()
                    try:
                        link = div.find("a")["href"]
                        list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                    except Exception:
                        list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
