"""
Parser template for RansomLook.

How to create a new parser:
1. Copy this file and rename it to match the group name exactly
   (e.g., "mygroup.py" for a group named "mygroup")
2. The filename MUST match the group name in the database
3. Implement the parsing logic in main()
4. Files to parse are in source/ and named: <groupname>-<slug>

Each parser must return a list of dicts with at least:
  - "title":       victim name (required)
  - "description": additional info (required, can be empty string)
  - "link":        link to the victim page (optional)
  - "slug":        source filename (optional, helps with dedup)
"""

import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

# The parser name is derived from the module name
PARSER_NAME = __name__.split(".")[-1]


def main() -> list[dict[str, str]]:
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            # --- Parsing logic goes here ---
            #
            # Example: extract all entries from a list
            #
            # for item in soup.find_all('div', {'class': 'post'}):
            #     title = item.find('h2').text.strip()
            #     description = item.find('p').text.strip()
            #     list_div.append({
            #         'title': title,
            #         'description': description,
            #         'link': item.find('a')['href'],
            #         'slug': filename,
            #     })
            #
            # Example: JSON embedded in <pre> tag
            #
            # import json
            # data = json.loads(soup.pre.text)
            # for entry in data:
            #     list_div.append({
            #         'title': entry['name'],
            #         'description': entry.get('details', ''),
            #     })

            pass  # Replace with your parsing logic

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
