import json
import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def _plain(text: str) -> str:
    """Strip any HTML markup that may sit in a description, flatten to one line."""
    if text and ("<" in text and ">" in text):
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    return " ".join(text.split())


def _first_link(soup: BeautifulSoup) -> str:
    """Return the first victim website link, ignoring the ephemeral s3.php token."""
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.startswith("http"):
            return href
    return ""


def parse_json(content: str, filename: str) -> list[dict[str, str]]:
    """
    Parse the index.php?api=1 JSON feed. Accepts both the raw API shape
    (post.content is HTML) and the cleaned shape produced by
    tools/fetch_deadlock_json.py (post.description / post.link already set).
    """
    list_div: list[dict[str, str]] = []
    data = json.loads(content)
    posts = data.get("posts") if isinstance(data, dict) else data
    if not isinstance(posts, list):
        return list_div
    for entry in posts:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        if not title:
            continue
        if entry.get("description") is not None or entry.get("link") is not None:
            description = str(entry.get("description") or "")
            link = str(entry.get("link") or "").strip()
        else:
            body = BeautifulSoup(str(entry.get("content") or ""), "html.parser")
            description = body.get_text(" ", strip=True)
            link = _first_link(body)
        list_div.append({"title": title, "description": _plain(description), "link": link, "slug": filename})
    return list_div


def parse_html(content: str, filename: str) -> list[dict[str, str]]:
    """Parse the rendered blog cards (div.post -> .post-title.font + .post-text)."""
    list_div = []
    soup = BeautifulSoup(content, "html.parser")
    for post in soup.find_all("div", class_="post"):
        badge = post.find("span", class_="badge")
        if badge and "pub" not in (badge.get("class") or []):
            continue
        heading = post.find("div", class_="post-title")
        if not heading:
            continue
        title = heading.get_text(strip=True)
        if not title:
            continue
        body = post.find("div", class_="post-body") or post
        text = body.find("p", class_="post-text")
        list_div.append(
            {
                "title": title,
                "description": _plain(text.get_text(" ", strip=True) if text else ""),
                "link": _first_link(body),
                "slug": filename,
            }
        )
    return list_div


def main() -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                content = file.read()

            parsed = []
            if content.lstrip().startswith(("{", "[")):
                # raw API dump (index.php?api=1)
                try:
                    parsed = parse_json(content, filename)
                except Exception:
                    parsed = []
            else:
                soup = BeautifulSoup(content, "html.parser")
                if soup.find("div", class_="post"):
                    # rendered blog page (cards). Its <pre> is only the API doc
                    # example, so never treat that as data.
                    parsed = parse_html(content, filename)
                else:
                    # API rendered through a browser : JSON wrapped in <pre>
                    pre = soup.find("pre")
                    if pre and pre.text.lstrip().startswith(("{", "[")):
                        try:
                            parsed = parse_json(pre.text, filename)
                        except Exception:
                            parsed = []

            for entry in parsed:
                prev = entries.get(entry["title"])
                if prev is None or len(entry["description"]) > len(prev["description"]):
                    entries[entry["title"]] = entry
        except Exception:
            logger.debug("Failed during : " + filename)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
