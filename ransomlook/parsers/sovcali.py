import os
import re

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

POST = re.compile(r'cat\s*:\s*"([^"]*)".*?excerpt\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                for title, description in POST.findall(file.read()):
                    list_div.append({"title": title.strip(), "description": description.replace('\\"', '"').strip()})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
