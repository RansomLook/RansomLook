import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for h2 in soup.find_all("h2"):
                entry = h2.find_parent("div")
                if not entry:
                    continue
                title = h2.get_text(strip=True)
                if not title:
                    continue

                parts = []
                for block in entry.find_all("div", class_="parsed-post-text"):
                    text = block.get_text("\n", strip=True)
                    if text:
                        parts.append(text)
                for li in entry.find_all("li"):
                    a = li.find("a")
                    if a and a.get_text(strip=True):
                        parts.append("File: " + a.get_text(strip=True))

                list_div.append({
                    "title": title,
                    "description": "\n".join(parts),
                    "slug": filename,
                })

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
