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
                divs_name = soup.find_all("div", {"class": "publications-inner"})
                for div in divs_name:
                    title = (
                        div.find(
                            "div", {"class": "self-stretch h-14 flex-col justify-center items-start gap-[5px] flex"}
                        )
                        .find("a")
                        .text.strip()
                    )
                    description = div.find(
                        "div", {"class": "self-stretch text-[#97979a] text-base font-normal smalldesc leading-normal"}
                    ).text.strip()
                    link = div.find("a")["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})

                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
