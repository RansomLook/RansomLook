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
                list_items = soup.find_all("li")
                for li in list_items:
                    post_link = li.find("a", href=lambda x: x and x.startswith("/post/"))
                    if post_link:
                        title_h1 = post_link.find("h1")
                        if title_h1:
                            title = title_h1.text.strip()
                            description = ""
                            link = post_link["href"]
                            list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
