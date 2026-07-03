import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

# Column order of the victim table: Name, Revenue, Sector, Stock Ticker,
# Data Size, # Of Files, Action.


def _score(entry: dict[str, str]) -> tuple[int, int]:
    absolute = 1 if entry.get("link", "").startswith("http") else 0
    return (absolute, len(entry.get("description", "")))


def main() -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                with open(html_doc, encoding="utf-8") as file:
                    soup = BeautifulSoup(file, "html.parser")

                for row in soup.find_all("tr"):
                    # A real victim row leads with a <td><strong>Name</strong>.
                    # This skips the <thead> row and the "View All →" row
                    # (colspan cell, no <strong>) served on the home page.
                    strong = row.find("strong")
                    if not strong:
                        continue
                    title = strong.text.strip()
                    if not title:
                        continue

                    cells = [td.text.strip() for td in row.find_all("td")]
                    labels = ["Revenue", "Sector", "Stock Ticker", "Data Size", "Files"]
                    parts = []
                    for label, value in zip(labels, cells[1:6]):
                        if value and value.upper() != "N/A":
                            parts.append(label + ": " + value)
                    description = " | ".join(parts)

                    link = ""
                    anchor = row.find("a", href=True)
                    if anchor:
                        link = anchor["href"]

                    entry = {"title": title, "description": description, "link": link, "slug": filename}
                    # The home page also lists a subset of victims (with a
                    # placeholder /companies link); dedupe by title and keep the
                    # richest record — one carrying a real mirror URL wins over a
                    # relative link, then the longer description breaks ties.
                    prev = entries.get(title)
                    if prev is None or _score(entry) > _score(prev):
                        entries[title] = entry
        except Exception:
            logger.debug("Failed during : " + filename)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
