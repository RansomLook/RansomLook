import os
from urllib.parse import quote

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    """
    Parser for the Exitium ransomware DLS.

    Victims are rendered server-side as div.target-card elements inside
    #targetGrid. Each card carries its data in attributes:
    - data-title  : victim name
    - data-text   : description (website / exfil summary)
    - data-date   : publish date (ISO 8601)
    - data-zip    : download link (may be empty)

    DOM fallbacks: span.card-name (title), p.target-text (description).
    """
    list_posts = []
    parser_name = __name__.split(".")[-1]  # 'exitium'

    for filename in os.listdir("source"):
        if not filename.startswith(parser_name + "-"):
            continue
        filepath = os.path.join("source", filename)
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        soup = BeautifulSoup(content, "html.parser")

        grid = soup.find("div", id="targetGrid")
        if not grid:
            continue

        for card in grid.find_all("div", class_="target-card"):  # type: ignore[union-attr]
            name = (card.get("data-title") or "").strip()
            if not name:
                span = card.find("span", class_="card-name")
                if span:
                    name = span.get_text(strip=True)
            if not name:
                continue

            post = {
                "title": name,
                "slug": filename,
                "link": "#" + quote(name),
            }

            # Description
            desc = (card.get("data-text") or "").strip()
            if not desc:
                desc_tag = card.find("p", class_="target-text")
                if desc_tag:
                    desc = desc_tag.get_text(strip=True)
            if desc:
                post["description"] = desc

            list_posts.append(post)

    return list_posts
