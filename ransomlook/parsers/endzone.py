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
                cards = soup.find_all("div", {"class": "glow-card"})
                for card in cards:
                    name_elem = card.find("h2", {"class": "company-name"})
                    title = name_elem.text.strip() if name_elem else ""
                    desc_elem = card.find("p", {"class": "description"})
                    description = desc_elem.text.strip() if desc_elem else ""
                    sample_btn = card.find("a", {"class": "sample-btn"})
                    link = sample_btn.get("href", "") if sample_btn else ""
                    if title:
                        list_div.append({
                            "title": title,
                            "description": description,
                            "link": link,
                            "slug": filename
                        })
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
