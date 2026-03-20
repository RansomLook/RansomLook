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
                divs_name = soup.find_all("td", {"valign": "top"})
                for div in divs_name:
                    title = div.find("font", {"size": 4}).text.strip()
                    link = div.find("a", {"style": "text-decoration: none;"})["href"]
                    for description in div.find_all("font", {"size": 2, "color": "#5B61F6"}):
                        if not description.b.text.strip().startswith("http"):
                            list_div.append(
                                {
                                    "title": title,
                                    "description": description.b.text.strip(),
                                    "link": link,
                                    "slug": filename,
                                }
                            )
                            break
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
