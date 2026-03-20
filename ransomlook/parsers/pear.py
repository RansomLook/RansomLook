import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        if filename.startswith(__name__.split(".")[-1] + "-"):
            html_doc = "source/" + filename
            file = open(html_doc, encoding="utf-8")
            soup = BeautifulSoup(file, "html.parser")

            divs_name = soup.find_all("td", {"class": "es-text-7589"})
            for div in divs_name:
                strong = div.find("strong")
                if strong is None:
                    continue
                title_str = strong.find(string=True, recursive=False)
                if title_str is None:
                    continue
                title = title_str.strip()
                paragraphs = div.find_all("p")
                description = paragraphs[1].text.strip() if len(paragraphs) > 1 else ""
                links = div.find_all("a")
                link = links[1]["href"] if len(links) > 1 else ""
                list_div.append({"title": title, "description": description, "link": link, "slug": filename})
            file.close()
    logger.debug(list_div)
    return list_div
