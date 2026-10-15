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
            for card in soup.select("article.leak-card"):
                title_el = card.select_one(".leak-card-title")
                if title_el is None:
                    continue
                title = title_el.text.strip()
                desc_el = card.select_one(".leak-card-desc")
                description = desc_el.text.strip() if desc_el else ""
                entry = {"title": title, "description": description, "slug": filename}
                try:
                    entry["link"] = card["onclick"].split("'")[1]
                except Exception:
                    pass
                list_div.append(entry)
            file.close()
    logger.debug(list_div)
    return list_div
