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
                divs_name = soup.find_all("td")
                for div in divs_name:
                    title = div.a.text.replace("[*]", "").strip()
                    if title.lower() in [
                        "soon",
                        "contact information",
                        "public pgp key",
                        "all updates",
                        "breaches and operations by pryx.",
                    ]:
                        continue
                    description = ""
                    link = div.a["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                divs_name = soup.find_all("div", {"class": "update-box"})
                for div in divs_name:
                    title = div.find("h3").text.strip()
                    description = div.find("p").text.strip()
                    link = div.find("a")["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
