import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        # try:
        if filename.startswith(__name__.split(".")[-1] + "-"):
            html_doc = "source/" + filename
            file = open(html_doc, encoding="utf-8")
            soup = BeautifulSoup(file, "html.parser")
            divs_name = soup.find_all("div", {"class": "accordion-item border"})
            for div in divs_name:
                title = div.find("h2").text.strip()
                try:
                    description = div.find_all("div", {"class": "col"})[1].text.strip()
                except Exception:
                    description = ""
                list_div.append({"title": title, "description": description})
            file.close()
    # except:
    #    print("Failed during : " + filename)
    #    pass
    logger.debug(list_div)
    return list_div
