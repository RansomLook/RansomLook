import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                with open(html_doc, encoding="utf-8") as file:
                    soup = BeautifulSoup(file, "html.parser")

                for card in soup.find_all("div", {"class": "victim-card"}):
                    try:
                        title = card.find("h2").text.strip()
                    except Exception:
                        logger.debug("Skipping card without title in : " + filename)
                        continue

                    # "PAID" is a filler placeholder card, not a real victim.
                    if title.upper() == "PAID":
                        continue

                    # Status: upcoming / leaked / negotiating / negotiated.
                    status = ""
                    badge = card.find("span", {"class": "status-badge"})
                    if badge:
                        status = badge.text.strip()

                    # card-meta holds up to two spans: [size, "N files"].
                    parts = []
                    if status:
                        parts.append(status)
                    meta = card.find("div", {"class": "card-meta"})
                    if meta:
                        for span in meta.find_all("span", {"class": "meta-item"}):
                            value = span.text.strip()
                            if value:
                                parts.append(value)
                    description = " | ".join(parts)

                    link = ""
                    anchor = card.find("a", href=True)
                    if anchor:
                        link = anchor["href"]

                    list_div.append(
                        {"title": title, "description": description, "link": link, "slug": filename}
                    )
        except Exception:
            logger.debug("Failed during : " + filename)

    logger.debug(list_div)
    return list_div
