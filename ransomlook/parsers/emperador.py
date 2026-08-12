import os
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]
BASE_URL = "http://emprdr4p7iwlhpky33tswt3k2qdeljyjcdpoysabudmmrz4z32laexad.onion"

SIZE_RE = re.compile(r"\b\d+(?:\.\d+)?\s?[KMGT]B\b")
DATE_RE = re.compile(r"[A-Z][a-z]{2} \d{1,2}, \d{4} \d{1,2}:\d{2} [AP]M")


def parse_date(text: str) -> str:
    """'Aug 10, 2026 3:24 PM' -> '2026-08-10 15:24:00'."""
    try:
        return datetime.strptime(text, "%b %d, %Y %I:%M %p").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""


def countdown(timer: Tag | None) -> str:
    """The card shows a live countdown; the deadline itself is in data-end."""
    end = timer.get("data-end") if isinstance(timer, Tag) else None
    if not end:
        return ""
    try:
        deadline = datetime.fromisoformat(str(end))
    except ValueError:
        return ""
    if deadline <= datetime.now(timezone.utc):
        return "Published"
    return "Publication scheduled: " + deadline.strftime("%Y-%m-%d %H:%M:%S %Z")


def main() -> list[dict[str, str]]:
    """
    Parser for the EMPERADOR DLS.

    Plain server-rendered HTML, no gate and no pagination: every victim is an
    <a class="card"> on the index, already carrying its full description (the
    grid only clips it with CSS). The single script on the page animates the
    countdown, so nothing has to be waited for -- the deadline is read from the
    timer's data-end attribute instead of its rendered text.
    """
    list_div = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        try:
            with open(os.path.join("source", filename), encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

            for card in soup.find_all("a", class_="card"):
                title_tag = card.find("div", class_="card-title")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                desc_tag = card.find("div", class_="card-desc")
                text = " ".join(card.get_text(" ", strip=True).split())
                size = SIZE_RE.search(text)
                date = DATE_RE.search(text)
                tags = [str(span["title"]) for span in card.select("span[title]")]

                parts = [
                    desc_tag.get_text(" ", strip=True) if desc_tag else "",
                    countdown(card.find("div", class_="timer")),
                    "Size: " + size.group(0) if size else "",
                    "Sectors: " + ", ".join(tags) if tags else "",
                ]

                list_div.append({
                    "title": title,
                    "description": "\n".join(part for part in parts if part),
                    "link": BASE_URL + str(card.get("href", "")),
                    "slug": filename,
                    "date": parse_date(date.group(0)) if date else "",
                })

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
