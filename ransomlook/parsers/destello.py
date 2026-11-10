import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    """
    Parser for the DESTELLO DLS (server-rendered).

    The wall lists one article.card per victim: div.vname (name),
    div.meta ("Sector · CC · size · files"), span.badge (status),
    [data-deadline] (ISO deadline) and a.more -> /v/<slug> (HTML case page,
    used as link for the screenshot).
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for card in soup.find_all("article", class_="card"):
                try:
                    name = card.find("div", class_="vname")
                    title = name.get_text(" ", strip=True) if name else ""
                    if not title:
                        continue

                    parts = []
                    meta = card.find("div", class_="meta")
                    if meta:
                        parts.append(meta.get_text(" ", strip=True))
                    badge = card.find("span", class_="badge")
                    if badge:
                        parts.append("Status: " + badge.get_text(strip=True))
                    timer = card.find(attrs={"data-deadline": True})
                    if timer and timer.get("data-deadline"):
                        parts.append("Deadline: " + str(timer["data-deadline"]).replace("T", " ").replace("Z", " UTC"))

                    entry = {"title": title, "description": " | ".join(parts), "slug": filename}
                    more = card.find("a", class_="more", href=True)
                    if more and str(more["href"]).startswith("/v/"):
                        entry["link"] = str(more["href"])
                    list_div.append(entry)
                except Exception as e:
                    logger.error("Error parsing card in %s: %s", filename, e)

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
