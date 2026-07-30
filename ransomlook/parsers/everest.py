import json
import os
import re

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

PAGE_JSON_RE = re.compile(r'<script data-page="app" type="application/json">(.*?)</script>', re.DOTALL)


def main() -> list[dict[str, str]]:
    """
    Parser for the Everest ransomware DLS.

    The site is now an Inertia.js/React SPA ("Chronicle"). The initial
    HTML response already embeds the full page payload as JSON in
    <script data-page="app" type="application/json"> -- server-side
    rendered by Inertia before any client JS runs -- so it's parsed
    directly instead of scraping the (JS-only) DOM.

    props.categories holds one entry per victim (title, slug, date,
    postCount, opens, locked). The full post body only lives on the
    per-category detail page (/news/<slug>), which the single
    index-page capture doesn't fetch, so the description is built from
    the metadata available on the index instead.
    """
    list_posts = []
    parser_name = __name__.split(".")[-1]  # 'everest'

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

        match = PAGE_JSON_RE.search(content)
        if not match:
            continue
        try:
            data = json.loads(match.group(1))
        except Exception:
            logger.debug("Failed parsing embedded JSON : " + filename)
            continue

        categories = data.get("props", {}).get("categories") or []
        for cat in categories:
            name = str(cat.get("title") or "").strip()
            slug = cat.get("slug")
            if not name or not slug:
                continue

            meta = []
            if cat.get("postCount") is not None:
                meta.append(f"{cat['postCount']} posts")
            if cat.get("date"):
                meta.append(str(cat["date"]))
            if cat.get("locked"):
                meta.append("password protected")

            post = {"title": name, "slug": filename, "link": f"/news/{slug}"}
            if meta:
                post["description"] = " - ".join(meta)

            list_posts.append(post)

    logger.debug(list_posts)
    return list_posts
