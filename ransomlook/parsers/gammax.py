import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []
    for filename in os.listdir("source"):
        if filename.startswith(__name__.split(".")[-1] + "-"):
            try:
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                divs_name = soup.find_all("article", {"class": "post-card"})
                for div in divs_name:
                    title = div.find("h2").text.strip()
                    description = div.find("p", {"class": "post-excerpt"}).text.strip()
                    link = div.find("a", {"class": "post-card-link"})["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})

                file.close()
            except Exception:
                pass
    logger.debug(list_div)
    return list_div
