import os
from datetime import datetime, timezone
from urllib.parse import quote

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    """
    Parser for the PixelLeaks DLS (server-rendered).

    Victims are article.lg-entry cards in the "Disclosures" and "Leaks" tabs
    (div.lg-name, div.lg-ctx, hidden div.lgm-data with the summary). The
    "Upcoming" tab only lists anonymous teasers ("Unnamed") and is skipped.

    Screenshots: link is '#Name' — the init_script switches to the card's tab
    and clicks it to open the details modal. The /dl/<id> archive links are
    never used as link.
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for card in soup.find_all("article", class_="lg-entry"):
                try:
                    name = card.find("div", class_="lg-name")
                    title = name.get_text(" ", strip=True) if name else ""
                    if not title:
                        continue

                    parts = []
                    ctx = card.find("div", class_="lg-ctx")
                    if ctx:
                        parts.append(ctx.get_text(" ", strip=True))
                    when = card.find("span", class_="lg-leakwhen")
                    if when:
                        parts.append(when.get_text(" ", strip=True))
                    else:
                        timer = card.find(attrs={"data-deadline": True})
                        if timer:
                            try:
                                ts = datetime.fromtimestamp(int(str(timer["data-deadline"])), tz=timezone.utc)
                                parts.append("Full data leak: " + ts.strftime("%Y-%m-%d %H:%M UTC"))
                            except ValueError:
                                pass
                    summary = card.find("div", class_="lgm-summary")
                    if summary:
                        parts.append(" ".join(p.get_text(" ", strip=True) for p in summary.find_all("p")))

                    list_div.append(
                        {
                            "title": title,
                            "description": "\n".join(parts),
                            "link": "#" + quote(title),
                            "slug": filename,
                        }
                    )
                except Exception as e:
                    logger.error("Error parsing entry in %s: %s", filename, e)

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
