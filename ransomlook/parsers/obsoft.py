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

            # Victim cards are server-rendered <div class="lb-card lb-card-*">
            # elements. Static announcement posts are <a class="lb-card
            # lb-card-static"> and are skipped (they are group news, not
            # victims).
            for card in soup.find_all("div", {"class": "lb-card"}):
                try:
                    title_tag = card.find("h3")
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)

                    # Status: Pending / Exposed / Leak / Resolved
                    phase = card.find("span", {"class": "lb-phase"})
                    status = phase.get_text(strip=True) if phase else ""

                    # Outcome note shown on resolved cards ("Data destroyed")
                    body = card.find("p", {"class": "lb-resolved-body"})

                    # Stolen data size ("32.84TB")
                    size = card.find("span", {"class": "lb-size"})

                    # Victim country from the flag tooltip
                    country = card.find("span", {"class": "lb-tip"})

                    # Publication deadline for pending cards (ISO timestamp)
                    countdown = card.find(attrs={"data-countdown": True})

                    # Last update time ("Nov 1, 2026 4:54 PM UTC")
                    updated = card.find("span", {"class": "lb-updated-text"})

                    parts = []
                    if status:
                        parts.append("Status: " + status)
                    if size:
                        parts.append("Size: " + size.get_text(strip=True))
                    if country and country.get("title"):
                        parts.append("Country: " + country["title"])
                    if updated:
                        parts.append("Updated: " + updated.get_text(strip=True))
                    if countdown and countdown.get("data-countdown"):
                        parts.append("Deadline: " + countdown["data-countdown"])
                    if body:
                        parts.append(body.get_text(strip=True))
                    description = " | ".join(parts)

                    list_div.append(
                        {
                            "title": title,
                            "description": description,
                            "slug": filename,
                        }
                    )
                except Exception as e:
                    logger.error("Error parsing card in %s: %s", filename, e)

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
