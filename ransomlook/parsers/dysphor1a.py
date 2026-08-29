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

            details = {}
            for block in soup.select("#rl-victim-details .rl-victim-detail"):
                name = block.find(["h1", "h2", "h3"])
                if not name:
                    continue
                body = " ".join(block.get_text(" ").split())
                if body:
                    details[" ".join(name.text.split()).upper()] = body

            for card in soup.select("article"):
                if "rl-victim-detail" in (card.get("class") or []):
                    continue
                heading = card.find("h3")
                if not heading:
                    continue
                title = " ".join(heading.text.split())
                if not title or title in seen:
                    continue
                seen.add(title)

                parts = []
                for tag in card.find_all("span"):
                    classes = tag.get("class") or []
                    if "inline-flex" not in classes:
                        continue
                    inner = tag.find_all("span")
                    if len(inner) >= 2:
                        label = " ".join(inner[0].text.split())
                        value = " ".join(inner[1].text.split())
                        if label and value:
                            parts.append(f"{label}: {value}")
                summary = card.find_all("p")
                if len(summary) > 1:
                    text = " ".join(summary[1].text.split())
                    if text:
                        parts.append(text)
                badge = card.select_one("span.clip-corner")
                if badge and badge.text.strip():
                    parts.append(" ".join(badge.text.split()))

                detail = details.get(title.upper())
                if detail:
                    parts.append(detail)

                list_div.append({"title": title, "description": " | ".join(parts), "slug": filename})
        except Exception:
            logger.debug("Failed during : " + filename)

    logger.debug(list_div)
    return list_div
