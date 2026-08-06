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
                articles = soup.find_all("article", {"class": "post-item"})
                for article in articles:
                    a = article.find("a")
                    if not a:
                        continue
                    title = a.text.strip()
                    description = ""
                    link = a["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception as e:
            logger.debug("Error in parsing file: " + filename + " | " + str(e))
    logger.debug(list_div)
    return list_div
