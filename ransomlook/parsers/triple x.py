import os
from bs4 import BeautifulSoup
from ransomlook.default.logging import get_logger

logger = get_logger(__name__)

def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                with open(html_doc, encoding="utf-8") as file:
                    soup = BeautifulSoup(file, "html.parser")

                posts = soup.find_all("div", class_="post")
                for post in posts:
                    title_el = post.find("h2", class_="post-title")
                    title = title_el.get_text(strip=True) if title_el else ""
                    if not title:
                        continue

                    desc_el = post.find("div", class_="post-content")
                    description = desc_el.get_text("\n", strip=True) if desc_el else ""

                    list_div.append({"title": title, "description": description})

        except Exception:
            logger.debug("Failed during: " + filename)

    logger.debug(list_div)
    return list_div
