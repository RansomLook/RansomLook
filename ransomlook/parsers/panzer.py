import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    """
    Panzer serves its victim list as plain JSON at /api/public/blog
    (React SPA, no server-rendered HTML). The saved source file is either
    the raw JSON body or that JSON wrapped in a <pre> tag by the browser.
    """
    list_div = []

    for filename in os.listdir("source"):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                raw = file.read()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                soup = BeautifulSoup(raw, "html.parser")
                pre = soup.find("pre")
                data = json.loads(pre.text) if pre else []

            for entry in data:
                title = str(entry.get("company_name") or "").strip()
                if not title:
                    continue
                description = str(entry.get("content") or "").strip()
                list_div.append({"title": title, "description": description, "slug": filename})
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
