import os

from bs4 import BeautifulSoup, Tag

from ransomlook.default.logging import get_logger

logger = get_logger(__name__)


def main() -> list[dict[str, str]]:
    """
    Parser for the Global Secret Group (GSG) ransomware DLS.

    Real victims are <a class="project-card"> elements inside
    div.projects-grid (h3.card-title, p.card-description, href to the
    detail page). The site also pads the grid with decoy entries —
    <div class="project-card locked-card"> with no title/data, just a
    "Classified" overlay — which we skip since they are div, not a
    (BeautifulSoup's tag filter already excludes them).
    """
    list_posts = []
    parser_name = __name__.split(".")[-1]  # 'globalsecretgroup'

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

        grid = soup.find("div", class_="projects-grid")
        if not isinstance(grid, Tag):
            continue

        # real cards are <a class="project-card">, fake/locked ones are
        # <div class="project-card locked-card"> -- filtering on the "a"
        # tag skips the fakes.
        for card in grid.find_all("a", class_="project-card"):
            title_tag = card.find("h3", class_="card-title")
            if not title_tag:
                continue
            name = title_tag.get_text(strip=True)
            if not name:
                continue

            post = {
                "title": name,
                "slug": filename,
                "link": str(card.get("href", "")),
            }

            desc_tag = card.find("p", class_="card-description")
            if desc_tag:
                post["description"] = desc_tag.get_text(" ", strip=True)

            list_posts.append(post)

    logger.debug(list_posts)
    return list_posts
