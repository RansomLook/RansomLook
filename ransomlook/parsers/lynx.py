import json
import os
import urllib.parse
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def _first(entry: dict, keys: list[str]) -> str:
    for key in keys:
        value = entry.get(key)
        if value:
            return str(value).strip()
    return ""


def _decode_description(value) -> str:
    """The API stores the description as a list of percent-encoded strings."""
    parts = value if isinstance(value, list) else [value]
    decoded = [urllib.parse.unquote(str(p)).strip() for p in parts if p]
    return " ".join(p for p in decoded if p)


def parse_json(content: str, filename: str) -> list[dict[str, str]]:
    """Parse the /api/v1/blog/get/announcements JSON feed.

    The endpoint may be returned raw or wrapped in a <pre> tag when fetched
    through a rendering browser, so the caller hands us the decoded JSON text.

    Observed shape (Lynx, shared with INC Ransom):
        {"payload": {"announcements": [
            {"_id": "...", "company": {"company_name": "..."},
             "description": ["url%20encoded%20text"], "leakAt": 1781193000000}, ...]}}
    """
    list_div = []
    data = json.loads(content)
    if isinstance(data, dict):
        # Drill into payload then into the first list-valued candidate key.
        if isinstance(data.get("payload"), dict):
            data = data["payload"]
        for key in ("announcements", "data", "targets", "items", "results", "leaks"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        return list_div
    for entry in data:
        if not isinstance(entry, dict):
            continue
        company = entry.get("company")
        if isinstance(company, dict):
            title = _first(company, ["company_name", "companyName", "name", "title"])
        else:
            title = _first(entry, ["name", "companyName", "company_name", "company", "title", "victim"])
        if not title:
            continue
        if "description" in entry:
            description = _decode_description(entry["description"])
        else:
            description = _first(entry, ["text", "note", "info", "content", "descr", "body"])
        link = _first(entry, ["url", "link", "path"])
        if not link:
            ident = _first(entry, ["_id", "id", "slug", "uuid"])
            if ident:
                link = "/leaks/" + ident
        item = {"title": title, "description": description, "link": link, "slug": filename}
        leak_at = entry.get("leakAt") or entry.get("createdAt")
        if isinstance(leak_at, (int, float)):
            # Epoch milliseconds -> ISO date for accurate post timestamps.
            item["date"] = datetime.fromtimestamp(leak_at / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        list_div.append(item)
    return list_div


def parse_html(content: str, filename: str) -> list[dict[str, str]]:
    list_div = []
    soup = BeautifulSoup(content, "html.parser")

    # Newer onion template: news__block chat__block
    for div in soup.find_all("div", {"class": "news__block chat__block"}):
        try:
            title = div.find("h4").text.strip()
            description = div.find("p", {"class": "chat__block-descr"}).text.strip()
            list_div.append(
                {"title": title, "description": description, "link": div.a["href"], "slug": filename}
            )
        except Exception:
            logger.debug("Failed news__block entry in : " + filename)

    # Legacy template: leak-item / leak-company
    for div in soup.find_all("div", {"class": "leak-item"}):
        try:
            title = div.find("h2", {"class": "leak-company"}).text.strip()
            try:
                description = div.find("p", {"class": "leak-description"}).text.strip()
            except Exception:
                description = ""
            link = div.find("a")["href"]
            list_div.append({"title": title, "description": description, "link": link, "slug": filename})
        except Exception:
            logger.debug("Failed leak-item entry in : " + filename)

    return list_div


def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                with open(html_doc, encoding="utf-8") as file:
                    content = file.read()

                # API feed: the JSON may sit raw or inside a <pre> wrapper.
                json_text = content
                stripped = content.lstrip()
                if not stripped.startswith(("{", "[")):
                    pre = BeautifulSoup(content, "html.parser").find("pre")
                    json_text = pre.text if pre else ""

                parsed = []
                if json_text.lstrip().startswith(("{", "[")):
                    try:
                        parsed = parse_json(json_text, filename)
                    except Exception:
                        parsed = []

                # Fall back to HTML scraping for the /leaks pages.
                if not parsed:
                    parsed = parse_html(content, filename)

                list_div.extend(parsed)
        except Exception:
            logger.debug("Failed during : " + filename)

    # A group may expose only the HTML /leaks page, only the JSON API, or both
    # at once. When both feeds are configured the same victim shows up twice
    # (API title is usually the bare domain, HTML title the display name), so
    # deduplicate and keep the richest record (the API one carries date/decoded
    # description).
    deduped: dict[str, dict[str, str]] = {}
    for entry in list_div:
        key = _norm_title(entry["title"])
        if key not in deduped or _richer(entry, deduped[key]):
            deduped[key] = entry
    result = list(deduped.values())
    logger.debug(result)
    return result


_TLDS = (
    ".co.uk", ".uk.com", ".com.au", ".co.za",
    ".com", ".org", ".net", ".eu", ".io", ".co", ".uk", ".us", ".info", ".biz", ".de", ".fr",
)


def _norm_title(title: str) -> str:
    """Collapse a victim title to a comparison key.

    The API exposes a bare domain (``www.commonwealth-partners.com``) while the
    HTML page shows a display name (``CommonWealth Partners``); stripping the
    scheme/www/TLD and turning separators into spaces makes both converge.
    """
    norm = title.strip().lower().rstrip("/")
    for prefix in ("https://", "http://", "www."):
        if norm.startswith(prefix):
            norm = norm[len(prefix):]
    # Drop a trailing TLD only when it looks like a domain (no spaces, has a dot).
    if "." in norm and " " not in norm:
        for tld in _TLDS:
            if norm.endswith(tld):
                norm = norm[: -len(tld)]
                break
    for sep in ("-", "_", ".", "'", "  "):
        norm = norm.replace(sep, " ")
    return " ".join(norm.split())


def _richer(candidate: dict[str, str], current: dict[str, str]) -> bool:
    # Prefer the record that carries a real leak date, then the longer description.
    if ("date" in candidate) != ("date" in current):
        return "date" in candidate
    return len(candidate.get("description", "")) > len(current.get("description", ""))
