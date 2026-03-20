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
                divs_name = soup.find_all("div", {"class": "modal fade"})
                try:
                    for div in divs_name:
                        title = div.find("h5").text.strip()
                        description = div.find("pre", {"class": "text-break mb-2"}).text.strip()
                        try:
                            link = div.find("a")["href"]
                            if not link.startswith("http"):
                                link = "http://" + link
                            list_div.append(
                                {"title": title, "description": description, "link": link, "slug": filename}
                            )
                        except Exception:
                            list_div.append({"title": title, "description": description})
                except Exception:
                    pass
                divs_name = soup.find_all("div", {"class": "col"})
                for div in divs_name:
                    title = str(div.find("div", {"class": "card-title"}).text.strip().split("\t")[-1])
                    description = div.find("div", {"class": "card-text"}).text.strip()
                    try:
                        link = div.find("a")["href"]
                        if not link.startswith("http"):
                            link = "http://" + link
                        list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                    except Exception:
                        list_div.append({"title": title, "description": description})

                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
