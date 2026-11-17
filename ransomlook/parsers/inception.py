import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    """
    Parser for the Inception DLS (server-rendered, single page).

    One details.entry per victim: span.entry-name (name), span.entry-label
    (status, e.g. "leaked"), div.detail-desc (summary of the stolen data),
    div.detail-grid > div.detail-item (label/value pairs: Size, Files,
    Deadline). The "Download archive" button points to a separate file
    server (data download), so it is never used as link; no per-victim HTML
    page exists.
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for entry in soup.find_all("details", class_="entry"):
                try:
                    name = entry.find("span", class_="entry-name")
                    title = name.get_text(" ", strip=True) if name else ""
                    if not title:
                        continue

                    parts = []
                    for item in entry.find_all("div", class_="detail-item"):
                        label = item.find("div", class_="detail-label")
                        value = item.find("div", class_="detail-value")
                        if label and value and value.get_text(strip=True):
                            parts.append(f"{label.get_text(' ', strip=True)}: {value.get_text(' ', strip=True)}")
                    status = entry.find("span", class_="entry-label")
                    if status and status.get_text(strip=True):
                        parts.append("Status: " + status.get_text(" ", strip=True))

                    description = " | ".join(parts)
                    desc = entry.find("div", class_="detail-desc")
                    if desc:
                        text = desc.get_text(" ", strip=True)
                        if text:
                            description = f"{description}\n{text}" if description else text

                    list_div.append({"title": title, "description": description, "slug": filename})
                except Exception as e:
                    logger.error("Error parsing entry in %s: %s", filename, e)

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
