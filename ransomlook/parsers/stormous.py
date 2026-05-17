import os
import re

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                with open(html_doc, encoding="utf-8") as file:
                    content = file.read()

                # Extract data from JavaScript array using simple regex
                # Look for name: "..." and desc: "..." patterns
                name_matches = re.findall(r'name:\s*["\']([^"\']+)["\']', content)
                desc_matches = re.findall(r'desc:\s*["\']([^"\']*)["\']', content)

                # Pair names and descriptions
                for i in range(min(len(name_matches), len(desc_matches))):
                    title = name_matches[i].strip()
                    description = desc_matches[i].strip()
                    if title:
                        list_div.append({"title": title, "description": description})

        except Exception:
            logger.debug("Failed during : " + filename)

    logger.debug(list_div)
    return list_div
