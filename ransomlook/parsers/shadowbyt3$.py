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
                divs_name = soup.find_all("div", {"class":"leak-card"})
                for div in divs_name:
                    title_el = div.find('h3')
                    title = title_el.text.strip() if title_el else ""
                    if not title:
                        continue
                    desc_el = div.find('div', {"class": "phrase"})
                    description = desc_el.get_text("\n", strip=True) if desc_el else ""
                    list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
