import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "http://unsafeipw6wbkzzmj7yqp7bz6j7ivzynggmwxsm6u2wwfmfqrxqrrhyd.onion"


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                divs_name = soup.find_all("a", {"class": "reel-link"})
                for a in divs_name:
                    reel = a.find("div", {"class": "reel"})
                    if reel is None:
                        continue
                    title = reel.find("h3").text.strip()
                    fields = [p.text.strip() for p in reel.find("div", {"class": "reel-left"}).find_all("p")]
                    status = reel.find("div", {"class": "countdown-value"})
                    if status is not None:
                        fields.append("Status: " + status.text.strip())
                    description = " | ".join(fields)
                    href = a.get("href", "")
                    link = BASE_URL + href if href.startswith("/") else href
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
