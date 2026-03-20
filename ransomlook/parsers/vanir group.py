import json
import os
import re

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []
    for filename in os.listdir("source"):
        if filename.startswith(__name__.split(".")[-1] + "-"):
            html_doc = "source/" + filename
            file = open(html_doc, encoding="utf-8")
            if ".js" in filename:
                content = file.read()
                matches = re.search("projects:(.*)}}},P", content, re.IGNORECASE)
                if matches is None:
                    logger.debug("No match for pattern in %s", filename)
                    file.close()
                    continue
                myjson = (
                    matches.group(1)
                    .replace("projectName:", '"projectName":')
                    .replace("projectDescription:", '"projectDescription":')
                    .replace("githubLink:", '"githubLink":')
                    .replace("websiteLink:", '"websiteLink":')
                    .replace("tags:", '"tags":')
                )

                data = json.loads(myjson)
                for entry in data:
                    title = entry["projectName"].strip()
                    description = entry["projectDescription"].strip()
                    list_div.append({"title": title, "description": description})
            file.close()
    logger.debug(list_div)
    return list_div
