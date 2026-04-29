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

                anchors = soup.find_all("a", {"class": "card"})
                for nav in soup.find_all("div", {"class": "nav-item"}):
                    anchors.extend(nav.find_all("a"))

                for anchor in anchors:
                    img = anchor.find("img")
                    if img is None:
                        continue
                    title = (img.get("alt") or "").strip()
                    if not title:
                        continue
                    link = (anchor.get("href") or "").strip()
                    list_div.append(
                        {"title": title, "description": "", "link": link, "slug": filename}
                    )
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
