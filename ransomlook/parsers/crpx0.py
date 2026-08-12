import os
import re

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]
BASE_URL = "http://tlxoddx4odmc2qvsmtsbgwwsv5j45osb5sox7mz6izxliuju5mkulzad.onion"


def field(card: Tag, icon: str) -> str:
    """Card metadata is only identifiable by its Font Awesome icon."""
    tag = card.find("i", class_=icon)
    return tag.parent.get_text(" ", strip=True) if isinstance(tag, Tag) and tag.parent else ""


def main() -> list[dict[str, str]]:
    """
    Parser for the CRPxO DLS.

    Plain PHP, server-rendered, no gate. Victims are div.victim-card on
    index.php, paginated 10 per page through ?p=N -- and sorted OLDEST FIRST, so
    new victims land on the LAST page. The group therefore needs one location per
    page (out-of-range pages simply render an empty grid).

    Full write-ups live on victim.php?slug=..., which is what 'link' points to.
    """
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        try:
            with open(os.path.join("source", filename), encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

            for card in soup.find_all("div", class_="victim-card"):
                heading = card.find("h3")
                if not heading:
                    continue
                title = heading.get_text(strip=True)

                timer = card.find("div", class_="countdown-timer")
                deadline = str(timer.get("data-deadline", "")) if isinstance(timer, Tag) else ""
                status = str(timer.get("data-status", "")) if isinstance(timer, Tag) else ""

                parts = [
                    "Status: " + status if status else "",
                    "Location: " + field(card, "fa-location-dot"),
                    "Sector: " + field(card, "fa-industry"),
                    "Volume: " + field(card, "fa-server"),
                    "Deadline: " + deadline if deadline else "",
                ]

                link = card.find("a", href=re.compile(r"victim\.php"))
                entries[title] = {
                    "title": title,
                    "description": "\n".join(part for part in parts if part.split(": ", 1)[-1]),
                    "link": f"{BASE_URL}/{link['href']}" if isinstance(link, Tag) else "",
                    "slug": filename,

                }

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
