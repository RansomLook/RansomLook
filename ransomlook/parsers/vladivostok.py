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
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                file.close()
                for row in soup.find_all("li", {"class": "post-row"}):
                    link_tag = row.find("a", {"class": "post-title"})
                    if link_tag is None:
                        continue
                    title = link_tag.get_text(strip=True)
                    summary = row.find("p", {"class": "post-summary"})
                    description = summary.get_text(strip=True) if summary else ""
                    list_div.append({
                        "title": title,
                        "description": description,
                        "link": link_tag.get("href", ""),
                        "slug": filename,
                    })
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
