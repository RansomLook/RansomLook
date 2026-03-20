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
                divs_name = soup.find_all("div", {"class": "blog-card p-3 col-md-9"})
                logger.debug(divs_name)
                for div in divs_name:
                    title = div.find("div", {"class": "post-header col-md-12 no-pad px-3"}).a.text.strip()
                    description = div.find(
                        "div", {"class": "post-short-description col-md-12 no-pad px-3 mt-5"}
                    ).p.text.strip()
                    list_div.append({"title": title, "description": description})
                divs_name = soup.find_all("div", {"class": "container product mt-4"})
                for div in divs_name:
                    title = div.find("div", {"class": "product-header"}).a.text.strip()
                    description = div.find(
                        "div", {"class": "product-list-description col-md-7 mt-3 no-pad"}
                    ).p.text.strip()
                    list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
