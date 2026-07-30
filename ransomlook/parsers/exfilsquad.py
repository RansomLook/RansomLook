import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    """
    Parser for the ExfilSquad ransomware/extortion DLS.

    Single static page, no JS gate, no per-victim detail page. Each
    victim is a div.entry with div.company-name (title), .meta spans
    (revenue/size), img.flag-img (country code) and div.desc (warning +
    data summary text).

    No "link" is set: the a.download href points straight at a raw
    sample archive (.7z/.torrent/.jsonl), not an HTML page. Setting
    "link" makes ransomlook.screen() enqueue it as a Lacus capture,
    which just downloads the file over Tor -- so it's deliberately
    left out.
    """
    list_posts = []
    parser_name = __name__.split(".")[-1]  # 'exfilsquad'

    for filename in os.listdir("source"):
        if not filename.startswith(parser_name + "-"):
            continue
        filepath = os.path.join("source", filename)
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            logger.debug("Failed reading : " + filename)
            continue

        soup = BeautifulSoup(content, "html.parser")

        for entry in soup.find_all("div", class_="entry"):
            title_tag = entry.find("div", class_="company-name")
            if not title_tag:
                continue
            name = title_tag.get_text(strip=True)
            if not name:
                continue

            post = {"title": name, "slug": filename}

            flag_tag = entry.find("img", class_="flag-img")
            country = str(flag_tag.get("alt", "")) if flag_tag else ""
            desc_tag = entry.find("div", class_="desc")
            desc_text = desc_tag.get_text(" ", strip=True) if desc_tag else ""
            description_parts = [part for part in (country, desc_text) if part]
            if description_parts:
                post["description"] = " - ".join(description_parts)

            list_posts.append(post)

    logger.debug(list_posts)
    return list_posts
