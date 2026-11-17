import os
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def _text(node: Tag | None) -> tuple[str, bool]:
    """
    Rebuild a value rendered one character per <span>.

    Returns the visible text and whether part of it is still redacted
    (span.masked-char blocks, or "*" placeholders in a half-hidden name).
    """
    if node is None:
        return "", False
    masked = node.find("span", class_="masked-char") is not None
    chars = node.find_all("span", class_="shown-char")
    text = "".join(c.get_text() for c in chars) if chars else ("" if masked else node.get_text())
    text = text.strip()
    return text, masked or "*" in text


def main() -> list[dict[str, str]]:
    """
    Parser for the Curious Worm DLS (server-rendered, single page).

    One div.target-card per victim (pending-state / leaked-state):
    div.field > span.label + span.value (Company = victim domain, Revenue,
    Status badge), div.description-box (size + company profile),
    div.countdown[data-leak-time] (epoch of publication, pending only).
    Every value is emitted one character per span.shown-char; redacted parts
    are span.masked-char blocks or "*" inside the name.

    Cards whose company name is still partly hidden are kept with the name
    as displayed (e.g. "ex*********s.com"); their redacted revenue and
    description are left out. The download button
    (/download/<id>) is a data download and is never used as link; no
    per-victim HTML page exists. The download counter is left out because it
    changes on every scrape.
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for card in soup.find_all("div", class_="target-card"):
                try:
                    fields: dict[str, tuple[str, bool]] = {}
                    for field in card.find_all("div", class_="field"):
                        label = field.find("span", class_="label")
                        if label:
                            key = label.get_text(strip=True).rstrip(":").lower()
                            fields[key] = _text(field.find("span", class_="value"))

                    title, _ = fields.get("company", ("", False))
                    if not title:
                        continue

                    parts = []
                    revenue, hidden = fields.get("revenue", ("", False))
                    if revenue and not hidden:
                        parts.append("Revenue: " + revenue)
                    status = card.find("span", class_="status-badge")
                    if status and status.get_text(strip=True):
                        parts.append("Status: " + status.get_text(strip=True))
                    countdown = card.find("div", class_="countdown", attrs={"data-leak-time": True})
                    if countdown and str(countdown["data-leak-time"]).isdigit():
                        when = datetime.fromtimestamp(int(str(countdown["data-leak-time"])), tz=timezone.utc)
                        parts.append("Deadline: " + when.strftime("%Y-%m-%d %H:%M UTC"))

                    description = " | ".join(parts)
                    about, hidden = _text(card.find("div", class_="description-box"))
                    if about and not hidden:
                        description = f"{description}\n{about}" if description else about

                    list_div.append({"title": title, "description": description, "slug": filename})
                except Exception as e:
                    logger.error("Error parsing card in %s: %s", filename, e)

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
