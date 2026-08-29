import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []
    seen: set[str] = set()

    for filename in sorted(os.listdir("source")):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

            blob = soup.select_one("#rl-projects")
            if blob and blob.text.strip():
                try:
                    items = json.loads(blob.text)
                except Exception:
                    items = []
                for item in items if isinstance(items, list) else []:
                    if not isinstance(item, dict):
                        continue
                    index_id = str(item.get("indexId") or "").strip()
                    published = str(item.get("publishState") or "").lower() == "published" or item.get("isPublic") is True
                    name = str(item.get("name") or "").strip()
                    title = name if published and name else "Company ID : " + (index_id or "Unknown")
                    if not title or title in seen:
                        continue
                    seen.add(title)
                    parts = []
                    if item.get("country"):
                        parts.append("country: " + str(item["country"]).strip())
                    if item.get("fileSize") is not None:
                        parts.append("fileSize: " + str(item["fileSize"]))
                    parts.append("PUBLISHED" if published else "UNPUBLISHED")
                    if published and str(item.get("documentDescription") or "").strip():
                        parts.append(" ".join(str(item["documentDescription"]).split()))
                    entry = {"title": title, "description": " | ".join(parts), "slug": filename}
                    if index_id:
                        entry["link"] = "index.html?indexId=" + index_id
                    list_div.append(entry)
                continue

            for card in soup.select("div.pCard"):
                heading = card.select_one("div.pTitle")
                if not heading:
                    continue
                title = " ".join(heading.text.split())
                if not title or title in seen:
                    continue
                seen.add(title)

                parts = []
                country = card.select_one("div.pCountryTop")
                if country and country.text.strip():
                    parts.append(" ".join(country.text.split()))
                size = card.select_one("div.pairV")
                if size and size.text.strip():
                    parts.append("fileSize: " + " ".join(size.text.split()))
                status = card.select_one("div.pStatus")
                if status and status.text.strip():
                    parts.append(" ".join(status.text.split()))
                detail = card.select_one("div.pDetail")
                if detail and detail.text.strip():
                    parts.append(" ".join(detail.text.split()))

                list_div.append({"title": title, "description": " | ".join(parts), "slug": filename})
        except Exception:
            logger.debug("Failed during : " + filename)

    logger.debug(list_div)
    return list_div
