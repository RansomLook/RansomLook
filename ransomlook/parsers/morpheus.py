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
            # divs_name=soup.find_all('th', {"class": "align-middle", "style":"height:63px"})
            divs_name = soup.find_all("div", {"class": "post"})
            for div in divs_name:
                title_div = div.find("div", {"class": "post__header__title vkuiDiv vkuiRootComponent"})
                if title_div is None:
                    continue
                title = title_div.text.strip()
                desc_div = div.find("div", {"class": "post__text parsed-post-text vkuiDiv vkuiRootComponent"})
                description = desc_div.text.strip() if desc_div else ""
                list_div.append({"title": title, "description": description})
            file.close()
    logger.debug(list_div)
    return list_div
