import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PARSER_NAME = __name__.split(".")[-1]


def _human_size(num) -> str:
    try:
        size = float(num)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def json_description(post: dict) -> str:
    parts = []
    status = post.get("status")
    parts.append(str(post.get("category") or ("LEAK" if status == "publish" else status or "")).upper())
    # published posts carry "date"; pending ones carry "publish_date"
    if post.get("date"):
        parts.append(str(post["date"]))
    elif post.get("publish_date"):
        parts.append("Publication scheduled: " + str(post["publish_date"]))
    if post.get("excerpt"):
        parts.append(str(post["excerpt"]).strip())
    tree = post.get("file_tree") or {}
    if tree.get("file_count"):
        size = _human_size(tree.get("total_size"))
        parts.append(f"Files: {tree['file_count']}" + (f" / {size}" if size else ""))
    att = post.get("attachments") or {}
    if att.get("count"):
        parts.append(f"Attachments: {att['count']}")
    return "\n".join(p for p in parts if p)


def html_description(article) -> str:
    parts = []
    for sel, prefix in ((".post-category", ""), (".post-date", "")):
        el = article.select_one(sel)
        if el:
            parts.append(el.get_text(strip=True))
    cd = article.select_one(".post-countdown-value")
    if cd:
        parts.append("Publication scheduled: " + str(cd.get("data-deadline") or cd.get_text(strip=True)))
    desc = article.select_one(".listing-description")
    if desc:
        parts.append(desc.get_text(strip=True))
    return "\n".join(p for p in parts if p)


def main() -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        if not filename.startswith(PARSER_NAME + "-"):
            continue
        try:
            with open(os.path.join("source", filename), encoding="utf-8") as file:
                content = file.read()
            soup = BeautifulSoup(content, "html.parser")

            # The site is gated by a slider captcha solved by the location
            # init_script, which lands Lacus on /api/posts (JSON). Browsers wrap a
            # JSON response in <pre>; fall back to scanning the raw text, and to the
            # server-rendered HTML catalog if that is what was captured instead.
            payload = None
            holder = soup.find("pre")
            raw = holder.get_text() if holder else content
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and isinstance(data.get("posts"), list):
                    payload = data
            except (ValueError, TypeError):
                payload = None

            if payload is not None:
                for post in payload["posts"]:
                    title = str(post.get("title") or "").strip()
                    if not title:
                        continue
                    entries[title] = {
                        "title": title,
                        "description": json_description(post),
                        "link": "",
                        "slug": filename,
                    }
            else:
                for article in soup.select("article.post-listing"):
                    title_el = article.select_one(".listing-title")
                    title = title_el.get_text(strip=True) if title_el else ""
                    if not title:
                        continue
                    entries[title] = {
                        "title": title,
                        "description": html_description(article),
                        "link": "",
                        "slug": filename,
                    }
        except Exception as e:
            logger.error("Error parsing %s: %s", filename, e)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
