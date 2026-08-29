import os
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in sorted(os.listdir("source")):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

            for card in soup.select("article.lotus-card"):
                heading = card.find("h2")
                if not heading:
                    continue
                title = heading.text.strip()
                if not title:
                    continue

                parts = []
                for box in card.select("div.lotus-meta-box"):
                    parts.append(" ".join(box.text.split()))
                prose = card.select_one("div.prose")
                if prose and prose.text.strip():
                    parts.append(" ".join(prose.text.split()))
                badges = [
                    " ".join(b.text.split())
                    for b in card.find_all("span")
                    if b.get("class") and any(c.startswith("lotus-badge") for c in b["class"])
                ]
                if badges:
                    parts.append(" / ".join(badges))

                entry = {"title": title, "description": " | ".join(parts), "slug": filename}
                button = card.select_one("a.lotus-btn")
                if button and button.get("href"):
                    path = urlsplit(str(button["href"])).path
                    if path and path != "/":
                        entry["link"] = path
                list_div.append(entry)
        except Exception:
            logger.debug("Failed during : " + filename)

    logger.debug(list_div)
    return list_div
