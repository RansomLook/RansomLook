import json
import os
from datetime import datetime

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
                if "getallblogs" in filename:
                    logger.debug(filename)
                    jsonpart = soup.pre.contents  # type: ignore
                    data = json.loads(jsonpart[0])  # type: ignore
                    for entry in data["data"]["items"]:
                        date_str = entry["uploaded_date"]
                        date_obj = datetime.strptime(date_str, "%d %b, %Y %H:%M:%S %Z")
                        formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")
                        list_div.append(
                            {
                                "title": entry["company_name"].strip(),
                                "description": entry["description"].strip(),
                                "link": entry["id"],
                                "slug": filename,
                                "date": formatted_date,
                            }
                        )
                file.close()
        except Exception:
            logger.debug("can not open " + filename)
    logger.debug(list_div)
    return list_div
