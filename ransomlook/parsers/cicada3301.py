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
                divs_name = soup.find_all(
                    "div", {"class": "block relative p-8 bg-gray-800 rounded-lg transition duration-300 ease-in-out"}
                )
                for div in divs_name:
                    title = div.find("h2").text.strip()
                    description = div.find("p").text.strip()
                    a = div.find_all("a")
                    try:
                        link = a[1]["href"]
                        list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                    except Exception:
                        list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
