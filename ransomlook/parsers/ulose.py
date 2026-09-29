import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = "source/" + filename
        try:
            with open(html_doc, encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")
            try:
                jsonpart = soup.pre.contents  # type: ignore
                data = json.loads(jsonpart[0])  # type: ignore
            except Exception:
                # fall back to a raw JSON body without a <pre> wrapper
                file2 = open(html_doc, encoding="utf-8")
                data = json.loads(file2.read())
                file2.close()

            for entry in data["articles"]:
                title = entry["title"].strip()
                if not title:
                    continue

                parts = []
                desc = entry.get("description", "")
                if desc:
                    parts.append(desc.strip())
                if entry.get("country"):
                    parts.append("Country: " + entry["country"].strip())
                if entry.get("status"):
                    parts.append("Status: " + entry["status"].strip())
                if entry.get("createdAt"):
                    parts.append("Created: " + entry["createdAt"].strip())

                list_div.append(
                    {
                        "title": title,
                        "description": "\n".join(parts),
                        "slug": filename,
                    }
                )
        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
