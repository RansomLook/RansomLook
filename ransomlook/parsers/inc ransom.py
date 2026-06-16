import json
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def _first(entry: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = entry.get(key)
        if value:
            return str(value).strip()
    return ""


def _decode_parts(value: Any) -> list[str]:
    """The API stores text fields as lists of percent-encoded strings."""
    parts = value if isinstance(value, list) else [value]
    return [urllib.parse.unquote(str(p)).strip() for p in parts if p]


def parse_json(content: str, filename: str) -> list[dict[str, str]]:
    """Parse the /api/v1/blog/get/announcements JSON feed.

    The endpoint may be returned raw or wrapped in a <pre> tag when fetched
    through a rendering browser, so the caller hands us the decoded JSON text.

    Observed shape:
        {"payload": {"announcements": [
            {"_id": "...", "company": {"company_name": "..."},
             "description": ["url%20encoded%20text", ...], "leakAt": 1781524800000}, ...]}}

    INC quirks: company_name is percent-encoded and frequently junk ("3", a
    truncated name, ...) while the real victim (usually a domain) sits in the
    first description line.
    """
    list_div: list[dict[str, str]] = []
    data = json.loads(content)
    if isinstance(data, dict):
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

        desc_parts = _decode_parts(entry.get("description"))

        company = entry.get("company")
        if isinstance(company, dict):
            title = _first(company, ["company_name", "companyName", "name", "title"])
        else:
            title = _first(entry, ["name", "companyName", "company_name", "company", "title", "victim"])
        title = urllib.parse.unquote(title).strip()
        # Junk company_name -> fall back to the first description line (the domain).
        if len(title) <= 2 or title.isdigit():
            title = next((p for p in desc_parts if p), title)
        if not title:
            continue

        if desc_parts:
            description = " ".join(desc_parts)
        else:
            description = _first(entry, ["text", "note", "info", "content", "descr", "body"])

        link = _first(entry, ["url", "link", "path"])
        if not link:
            ident = _first(entry, ["_id", "id", "slug", "uuid"])
            if ident:
                link = "/blog/disclosures/" + ident

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

    green = (
        "flex flex-col justify-between w-full h-56 border-t-4 border-2 border-t-green-500 "
        "dark:border-gray-900 dark:border-t-green-500 rounded-[20px] bg-white dark:bg-navy-800"
    )
    red = (
        "flex flex-col justify-between w-full h-56 border-t-4 border-2 border-t-red-500 "
        "dark:border-gray-900 dark:border-t-red-500 rounded-[20px] bg-white dark:bg-navy-800"
    )
    for css in (green, red):
        for div in soup.find_all("a", {"class": css}):
            try:
                section = div.find("span", {"class": "dark:text-gray-600"})
                title = section.text.strip()
                description = div.find("span", {"class": "text-sm dark:text-gray-600"}).text.strip()
                link = div["href"]
                list_div.append({"title": title, "description": description, "link": link, "slug": filename})
            except Exception:
                logger.debug("Failed disclosure card in : " + filename)

    for div in soup.find_all("a", {"class": "announcement__container"}):
        try:
            title = div.find("span", {"class": "text-xs text-white"}).text.strip()
            link = div["href"]
            list_div.append({"title": title, "description": "", "link": link, "slug": filename})
        except Exception:
            logger.debug("Failed announcement card in : " + filename)

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
                if not content.lstrip().startswith(("{", "[")):
                    pre = BeautifulSoup(content, "html.parser").find("pre")
                    json_text = pre.text if pre else ""

                parsed = []
                if json_text.lstrip().startswith(("{", "[")):
                    try:
                        parsed = parse_json(json_text, filename)
                    except Exception:
                        parsed = []

                # Fall back to HTML scraping for the /blog/disclosures page.
                if not parsed:
                    parsed = parse_html(content, filename)

                list_div.extend(parsed)
        except Exception:
            logger.debug("Failed during : " + filename)

    # The group may expose only the HTML disclosures page, only the JSON API, or
    # both. When both are configured the same victim appears twice, so keep the
    # richest record (the API one carries the leak date and decoded description).
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
    """Collapse a victim title to a comparison key so the domain form
    (``smithassociatescpa.com``) and a display name converge."""
    norm = title.strip().lower().rstrip("/")
    for prefix in ("https://", "http://", "www."):
        if norm.startswith(prefix):
            norm = norm[len(prefix):]
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
