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
                try:
                    div_name = soup.find_all("div", {"id": "breach"})
                    divs_name = div_name[1].find_all("a", {"class": "product-card"})
                    for div in divs_name:
                        try:
                            title = div.find("h2").text.strip()
                            description = ""
                            link = div["href"]
                            list_div.append(
                                {"title": title, "description": description, "link": link, "slug": filename}
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
                div_name = soup.find("div", {"id": "ransom"})  # type: ignore
                divs_name = div_name.find_all("a", {"class": "product-card"})  # type: ignore[attr-defined]
                for div in divs_name:
                    title = div.find("h2").text.strip()
                    description = ""
                    link = div["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
