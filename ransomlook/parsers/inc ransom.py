import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    """
    INC Ransom blog (Next.js).
    Location: <onion>/api/v2/blog/news?limit=100 (JSON, wrapped in <pre> by the browser).
    """
    list_div = []
    for filename in os.listdir("source"):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open(os.path.join("source", filename), encoding="utf-8") as f:
                content = f.read()
            pre = BeautifulSoup(content, "html.parser").find("pre")
            data = json.loads(pre.text if pre else content)
            for item in data.get("items", []):
                title = str((item.get("client") or {}).get("client_name") or "").strip()
                if not title:
                    continue
                list_div.append({
                    "title": title,
                    "description": str(item.get("description") or "").strip(),
                    "link": "/post/?id=" + str(item["id"]),
                    "slug": filename,
                })
        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)
    logger.debug(list_div)
    return list_div
