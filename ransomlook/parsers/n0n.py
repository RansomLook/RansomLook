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
                cards = soup.find_all("div", {"class": "card"})
                for card in cards:
                    vname_elem = card.find("div", {"class": "vname"})
                    title = vname_elem.text.strip() if vname_elem else ""
                    meta_elem = card.find("div", {"class": "meta"})
                    description = meta_elem.text.strip() if meta_elem else ""
                    if title:
                        list_div.append({
                            "title": title,
                            "description": description
                        })
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
