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
                raw = file.read()
                file.close()
                try:
                    soup = BeautifulSoup(raw, "html.parser")
                    raw = soup.pre.contents[0] if soup.pre else raw  # type: ignore
                except Exception:
                    pass
                try:
                    data = json.loads(raw)
                    items = data.get("items", data) if isinstance(data, dict) else data
                    for entry in items:
                        title = entry["name"]
                        description = (entry.get("info") or "").strip()
                        list_div.append({"title": title, "description": description})
                except Exception:
                    pass
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
