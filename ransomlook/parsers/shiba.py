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
                content = file.read()
                file.close()
                # source is the /api/companies JSON, sometimes wrapped in <pre> by the browser
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    soup = BeautifulSoup(content, "html.parser")
                    data = json.loads(soup.pre.contents[0])  # type: ignore
                for entry in data:
                    title = entry.get("target_name", "").strip()
                    sector = entry.get("sector", "").strip()
                    country = entry.get("country", "").strip()
                    header = " - ".join(x for x in (sector, country) if x)
                    description = entry.get("description", "").strip()
                    if header:
                        description = header + "\n" + description if description else header
                    list_div.append({
                        "title": title,
                        "description": description,
                        "link": entry.get("website", ""),
                        "slug": filename,
                    })
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
