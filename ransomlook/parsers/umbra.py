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

            for card in soup.find_all("article", class_="download-card"):
                title_tag = card.find("h2")
                if title_tag is None:
                    continue
                title = title_tag.get_text(strip=True)
                if not title:
                    continue

                desc_tag = card.find("div", class_="card-description")
                description = desc_tag.get_text(strip=True) if desc_tag else ""

                footer = card.find("footer", class_="card-updated")
                if footer:
                    footer_text = footer.get_text(strip=True)
                    if footer_text:
                        description = (
                            f"{description} | {footer_text}"
                            if description
                            else footer_text
                        )

                if "psa-card" in card.get("class", []):
                    description = f"[PSA] {description}" if description else "[PSA]"

                list_div.append(
                    {
                        "title": title,
                        "description": description,
                        "slug": filename,
                    }
                )

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
