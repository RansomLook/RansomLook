import os
import re

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

ABOUT_RE = re.compile(r"/about/announcement/([0-9a-f-]{36})/")


def _cell(row: Tag, name: str) -> str:
    td = row.find("td", class_="column-" + name)
    return td.get_text(" ", strip=True) if isinstance(td, Tag) else ""


def main() -> list[dict[str, str]]:
    """
    Everstake DLS: server-side rendered announcement tables on /. Each row's
    title points to /about/announcement/<uuid>/, a standalone detail page
    (public.js only opens it as a popup), used as the screenshot link.

    Unrevealed victims have part of their name replaced by
    <span class="blurred-fragment">Hidden name</span>; that fragment is
    rendered as '***' so the title stays readable ("in***s.com").
    """
    entries: dict[str, dict[str, str]] = {}

    for filename in os.listdir("source"):
        if not filename.startswith(__name__.split(".")[-1] + "-"):
            continue
        try:
            with open("source/" + filename, encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

            for row in soup.select("main tbody tr"):
                title_td = row.find("td", class_="column-title")
                if not isinstance(title_td, Tag):
                    continue
                for frag in title_td.find_all("span", class_="blurred-fragment"):
                    frag.replace_with("***")
                title = " ".join(title_td.get_text(" ", strip=True).split()).replace(" *** ", "***")
                if not title or title in entries:
                    continue

                desc = []
                for label, name in (("Category", "category"), ("Size", "size")):
                    value = _cell(row, name)
                    if value:
                        desc.append(label + ": " + value)
                countdown = row.find("time", attrs={"data-release": True})
                if isinstance(countdown, Tag):
                    desc.append("Release: " + str(countdown["data-release"]))
                status = _cell(row, "status")
                if status:
                    desc.append("Status: " + status)

                link = ""
                about = title_td.find("a", href=ABOUT_RE)
                if isinstance(about, Tag):
                    m = ABOUT_RE.search(str(about["href"]))
                    if m:
                        link = "/about/announcement/" + m.group(1) + "/"

                entries[title] = {"title": title, "description": " | ".join(desc), "link": link, "slug": filename}
        except Exception:
            logger.debug("Failed during : " + filename)

    list_div = list(entries.values())
    logger.debug(list_div)
    return list_div
