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
            divs_name = soup.find_all("div", {"class": "overflow-hidden"})
            for div in divs_name:
                h2 = div.find("h2")
                if h2 is None:
                    continue
                title = h2.text.strip()
                p = div.find("p")
                description = p.text.strip() if p else ""
                a = div.find("a")
                link = a["href"] if a else ""
                list_div.append({"title": title, "description": description, "link": link, "slug": filename})
            file.close()
    logger.debug(list_div)
    return list_div
