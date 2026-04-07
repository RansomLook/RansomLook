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
                for h3 in soup.find_all("h3"):
                    title = h3.get_text(strip=True)
                    if not title:
                        continue
                    parent = h3.parent
                    desc_tag = parent.find("p") if parent else None
                    description = desc_tag.get_text(strip=True) if desc_tag else ""
                    list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
