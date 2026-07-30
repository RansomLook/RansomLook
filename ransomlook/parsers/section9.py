import os

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    """
    Parser for the SECTION9 ransomware DLS.

    Victims are rendered server-side as a.card elements inside div.cards.
    Titles/domains are masked with asterisks until their countdown
    (data-reveal-at on span.countdown) expires. Country is in
    span.country, sector in p.card-summary, and the detail page link is
    the card's own href (/post/<id>).
    """
    list_posts = []
    parser_name = __name__.split(".")[-1]  # 'section9'

    for filename in os.listdir("source"):
        if not filename.startswith(parser_name + "-"):
            continue
        filepath = os.path.join("source", filename)
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            logger.debug("Failed reading : " + filename)
            continue

        soup = BeautifulSoup(content, "html.parser")

        grid = soup.find("div", class_="cards")
        if not isinstance(grid, Tag):
            continue

        for card in grid.find_all("a", class_="card"):
            title_tag = card.find("h2", class_="card-title")
            if not title_tag:
                continue
            name = title_tag.get_text(strip=True)
            if not name or name.startswith("*"):
                continue

            post = {
                "title": name,
                "slug": filename,
                "link": str(card.get("href", "")),
            }

            country_tag = card.find("span", class_="country")
            sector_tag = card.find("p", class_="card-summary")
            description_parts = [t.get_text(strip=True) for t in (country_tag, sector_tag) if t]
            if description_parts:
                post["description"] = " - ".join(description_parts)

            list_posts.append(post)

    logger.debug(list_posts)
    return list_posts
