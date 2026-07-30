import html
import json
import os

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def _plain(text: str) -> str:
    """Unescape HTML entities / strip any markup, flatten to one line."""
    if not text:
        return ""
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    return " ".join(html.unescape(text).split())


def main() -> list[dict[str, str]]:
    """
    D1R is a WooCommerce DLS whose product list is rendered client-side through
    admin-ajax (action=mytheme_get_products_page). The victim link only exists
    in that AJAX payload (the cards carry href="#"), so the location runs an
    init_script that fetches every page and injects the result as a JSON blob
    <script id="rl-d1r-data">. We consume that blob here; the rendered cards are
    only a title-only fallback.
    """
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

            blob = soup.find("script", id="rl-d1r-data")
            if isinstance(blob, Tag) and blob.string:
                for prod in json.loads(blob.string):
                    title = _plain(str(prod.get("title") or ""))
                    if not title:
                        continue
                    entries[title] = {
                        "title": title,
                        "description": _plain(str(prod.get("description") or "")),
                        "link": str(prod.get("link") or "").strip(),
                        "slug": filename,
                    }
                continue

            # fallback : rendered cards, title only (no link available in the DOM)
            for card in soup.find_all("div", class_="product-card"):
                title = _plain(str(card.get("data-title") or ""))
                if not title or title in entries:
                    continue
                entries[title] = {"title": title, "description": "", "link": "", "slug": filename}
        except Exception:
            logger.debug("Failed during : " + filename)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
