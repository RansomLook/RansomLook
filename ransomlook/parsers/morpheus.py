import html
import json
import os
import re
from typing import Any

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]

_IMAGE_RE = re.compile(r"!\[image#\d+\]")


def _clean(text: str) -> str:
    text = _IMAGE_RE.sub("", text).replace("**", "")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _from_json(raw: str) -> list[dict[str, Any]] | None:
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [i for i in data["items"] if isinstance(i, dict)]
    return None


def main() -> list[dict[str, str]]:
    """
    Parser for the MORPHEUS DLS (React/VKUI SPA, Firefox only: Chromium gets 403).

    Preferred location: <onion>/intrumpwetrust/api/posts?page=1&perPage=50
    (JSON {items, total, ...}; browsers wrap it in <pre>). Protected or
    disabled placeholders ("New publication", empty text) are skipped.
    Falls back to the rendered VKUI page (div.post) if HTML was captured.
    No per-post route exists (hash router only has /:page), so no link.
    """
    list_div: list[dict[str, str]] = []

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        html_doc = os.path.join("source", filename)
        try:
            with open(html_doc, encoding="utf-8") as f:
                content = f.read()

            # The JSON response is large (base64 image previews): slice the
            # <pre> body out instead of building a full soup.
            start = content.find("<pre")
            raw = content
            if start != -1:
                start = content.find(">", start) + 1
                end = content.rfind("</pre>")
                raw = html.unescape(content[start:end if end != -1 else None])
            items = _from_json(raw.strip())

            if items is not None:
                for item in items:
                    if item.get("isProtected") or item.get("isEnabled") is False:
                        continue
                    title = str(item.get("title") or "").strip()
                    if not title:
                        continue
                    desc = _clean(str(item.get("text") or ""))
                    date = str(item.get("date") or "")[:10]
                    if date:
                        desc = f"Published: {date}\n{desc}" if desc else f"Published: {date}"
                    list_div.append({"title": title, "description": desc, "slug": filename})
                continue

            soup = BeautifulSoup(content, "html.parser")
            for div in soup.find_all("div", class_="post"):
                if "protected-post" in (div.get("class") or []):
                    continue
                title_div = div.find("div", class_="post__header__title")
                if title_div is None:
                    continue
                title = title_div.get_text(strip=True)
                desc_div = div.find("div", class_="post__text")
                description = desc_div.get_text("\n", strip=True) if desc_div else ""
                if title:
                    list_div.append({"title": title, "description": description, "slug": filename})

        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    logger.debug(list_div)
    return list_div
