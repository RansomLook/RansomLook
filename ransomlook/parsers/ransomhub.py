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
                divs_name = soup.find_all("div", {"class": "card-body"})
                for div in divs_name:
                    try:
                        title = div.find("a").text.strip()
                        div.find("p", {"class": "card-text"}).text.strip()
                        list_div.append(
                            {"title": title, "description": "", "link": div.find("a")["href"], "slug": filename}
                        )
                    except Exception:
                        pass
                divs_name = soup.find_all("div", {"class": "col-12 col-md-6 col-lg-4"})
                for div in divs_name:
                    try:
                        title = div.find("div", {"class": "card-title text-center"}).text.strip()
                        list_div.append(
                            {"title": title, "description": "", "link": div.find("a")["href"], "slug": filename}
                        )
                    except Exception:
                        pass

                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
