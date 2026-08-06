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
                for lot in soup.find_all("article", class_="lot"):
                    title = lot.find("h3").text.strip()
                    desc_tag = lot.find("p", class_="desc")
                    description = desc_tag.text.strip() if desc_tag else ""
                    status = lot.get("data-status", "")
                    if status:
                        description = f"[{status}] {description}"
                    a = lot.find("a", class_="action-link")
                    link = a["href"].strip() if a else ""
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
