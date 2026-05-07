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
                cards = soup.select("a.card:not(.card-stub)")
                for card in cards:
                    name_el = card.find(class_="card-name")
                    desc_el = card.find(class_="card-desc")
                    href = card.get("href", "")
                    if isinstance(href, list):
                        href = href[0] if href else ""
                    list_div.append({
                        "title": name_el.get_text(strip=True) if name_el else "",
                        "description": desc_el.get_text(strip=True) if desc_el else "",
                        "link": href,
                        "slug": filename,
                    })
                file.close()
        except Exception as e:
            logger.debug("Error in parsing file: " + filename + " | " + str(e))
    logger.debug(list_div)
    return list_div
