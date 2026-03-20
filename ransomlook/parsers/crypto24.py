import json
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
                if "-data" in filename:
                    jsonpart = soup.pre.contents  # type: ignore
                    logger.debug(jsonpart)
                    data = json.loads(jsonpart[0])  # type: ignore
                    logger.debug(data)
                    for entry in data:
                        title = entry["company"]
                        description = entry["comment"]
                        list_div.append({"title": title, "description": description})
                else:
                    body = soup.find("tbody")
                    if body is not None:
                        divs_name = body.find_all("tr")  # type: ignore
                        for div in divs_name:
                            tds = div.find_all("td")
                            title = tds[1].text.strip()
                            description = ""
                            list_div.append({"title": title, "description": description})
                    divs_name = soup.find_all("div", {"class": "ant-card css-ut69n1"})
                    for div in divs_name:
                        title = div.find("h2").text.strip()
                        description = ""
                        list_div.append({"title": title, "description": description})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
