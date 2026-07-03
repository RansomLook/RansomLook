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
                raw = soup.pre.text if soup.pre else soup.get_text()
                data = json.loads(raw)
                for entry in data:
                    title = entry.get("title", "").replace("\n", "").strip()
                    description = entry.get("description", "").replace("\n", "").strip()
                    link = entry.get("confidential", "")
                    list_div.append(
                        {
                            "title": title,
                            "description": description,
                            "link": link,
                            "slug": filename,
                        }
                    )
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
