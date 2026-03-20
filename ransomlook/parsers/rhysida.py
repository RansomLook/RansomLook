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
                divs_name = soup.find_all("div", {"class": "border m-2 p-2"})
                for div in divs_name:
                    title = div.find("div", {"class": "m-2 h4"}).a.text.strip()
                    description = div.find("div", {"class": "m-2"}).text.strip()
                    try:
                        link = "archive.php?company=" + div.find("button")["data-company"]
                        list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                    except Exception:
                        list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
