import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    """
    Parser for the VORTEX DLS (server-rendered, single page).

    One div.card per victim: h3 > a.card-link ("NAME - size - files", href
    /c/<id> = HTML case page, used as link), div.card-meta (tag, date),
    optional <p> teaser, optional [data-deadline] countdown. The "GET DATA"
    buttons (/d/<id>) are data downloads and are never used as link.

    The title keeps only the part before the first " - " so that the post
    stays stable when the operators edit the size/file counts.
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for card in soup.find_all("div", class_="card"):
                try:
                    anchor = card.find("a", class_="card-link")
                    if not anchor:
                        continue
                    full = anchor.get_text(" ", strip=True)
                    title, _, size = full.partition(" - ")
                    title = title.strip()
                    if not title:
                        continue

                    parts = []
                    if size.strip():
                        parts.append(size.strip())
                    meta = card.find("div", class_="card-meta")
                    if meta:
                        tag = meta.find("span", class_="tag")
                        if tag:
                            parts.append("Tag: " + tag.get_text(strip=True))
                        when = meta.find("time")
                        if when:
                            parts.append("Published: " + when.get_text(strip=True))
                    countdown = card.find(attrs={"data-deadline": True})
                    if countdown:
                        parts.append(
                            "Deadline: " + str(countdown["data-deadline"]).replace("T", " ").replace("Z", " UTC")
                        )
                    description = " | ".join(parts)
                    teaser = card.find("p")
                    if teaser:
                        text = teaser.get_text("\n", strip=True)
                        if text:
                            description = f"{description}\n{text}" if description else text

                    entry = {"title": title, "description": description, "slug": filename}
                    href = str(anchor.get("href", ""))
                    if href.startswith("/c/"):
                        entry["link"] = href
                    list_div.append(entry)
                except Exception as e:
                    logger.error("Error parsing card in %s: %s", filename, e)

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
