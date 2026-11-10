import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    """
    Parser for the Climax DLS (static site, paginated: /, /page/2/, ...).

    One article.post per victim: h2.post-title > a (name, /p/<uuid>/ case
    page used as link), p.post-cat (sector), p.post-meta (company URL,
    date), p.post-data (files / size), span.status-box. Redacted entries
    (name hidden behind a countdown) are skipped until the name is published.
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for post in soup.find_all("article", class_="post"):
                try:
                    title = str(post.get("data-title") or "").strip()
                    anchor = post.select_one("h2.post-title a")
                    if not title or (anchor and anchor.find("span", class_="name-hidden")):
                        continue

                    parts = []
                    cat = post.find("p", class_="post-cat")
                    if cat:
                        parts.append("Sector: " + cat.get_text(" ", strip=True))
                    meta = post.find("p", class_="post-meta")
                    if meta:
                        for a in meta.find_all("a", href=True):
                            if a.get_text(strip=True) == "Company URL" and str(a["href"]).startswith("http"):
                                parts.append("Website: " + str(a["href"]))
                    data = post.find("p", class_="post-data")
                    if data:
                        parts.append(" · ".join(s.get_text(" ", strip=True) for s in data.find_all("span", class_=False)))
                    status = post.find("span", class_="status-box")
                    if status:
                        parts.append("Status: " + status.get_text(strip=True))

                    entry = {"title": title, "description": " | ".join(p for p in parts if p), "slug": filename}
                    if anchor and str(anchor.get("href", "")).startswith("/p/"):
                        entry["link"] = str(anchor["href"])
                    list_div.append(entry)
                except Exception as e:
                    logger.error("Error parsing post in %s: %s", filename, e)

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
