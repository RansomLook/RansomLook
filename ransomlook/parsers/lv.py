import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []
    for filename in os.listdir("source"):
        if filename.startswith(__name__.split(".")[-1] + "-"):
            html_doc = "source/" + filename
            logger.debug(filename)
            file = open(html_doc, encoding="utf-8")
            soup = BeautifulSoup(file, "html.parser")
            if "api" in filename:
                jsonpart = soup.pre.contents  # type: ignore
                data = json.loads(jsonpart[0])  # type: ignore
                for entry in data["posts"]:
                    list_div.append(entry["title"].strip())
            else:
                divs_name = soup.find_all("div", {"class": "blog-post blog-main posts_at_first"})
                for div in divs_name:
                    list_div.append(div.h2.a.text.strip())
            file.close()
    list_div = list(dict.fromkeys(list_div))
    logger.debug(list_div)

    return list_div
