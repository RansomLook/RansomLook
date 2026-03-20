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
            divs_name = soup.find_all("div", {"class": "row"})
            for div in divs_name:
                for item in div.find_all("a"):
                    item.text.strip()
                    description = ""
                    link = item["href"]
                    list_div.append(
                        {"title": item.text.strip(), "description": description, "link": link, "slug": filename}
                    )
            file.close()
    logger.debug(list_div)
    return list_div
