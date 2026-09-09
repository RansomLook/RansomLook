import os
import re

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

# Publication cards link to /<uuid> at the site root (they used to live under
# /publications/details/<id>).
UUID_HREF = re.compile(r"^/[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")


def main() -> list[dict[str, str]]:

    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                for card in soup.find_all("a", href=UUID_HREF):
                    try:
                        texts = [p.text.strip() for p in card.find_all("p")]
                        description = texts[2] if len(texts) > 2 else ""
                        if description.rstrip(":").lower() in ("revenue", "category"):
                            description = ""
                        list_div.append({"title": texts[1], "description": description,
                                         "link": card["href"], "slug": filename})
                    except Exception:
                        logger.debug("Failed entry in : " + filename)
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
