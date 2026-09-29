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
                divs_name = soup.find_all("div", {"class": "card"})
                for div in divs_name:
                    title = div.find(class_="card-title").text.strip()
                    description = div.find(class_="card-desc").text.strip()
                    # "Open" button anchors the per-victim modal (#modal-card-<id>);
                    # used as the link so the screenshot queue opens that modal.
                    link = div.find("a", {"class": "btn"})["href"]
                    list_div.append(
                        {"title": title, "description": description, "link": link, "slug": filename}
                    )
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
