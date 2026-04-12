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
                for card in soup.find_all("div", {"class": "card"}):
                    title_tag = card.find("h5", {"class": "card-title"})
                    if title_tag is None:
                        continue
                    title = title_tag.get_text(strip=True)
                    texts = card.find_all("p", {"class": "card-text"})
                    description = texts[1].get_text(strip=True) if len(texts) > 1 else ""
                    link_tag = card.find("a", {"class": "btn-secondary"})
                    link = link_tag["href"] if link_tag else ""
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
