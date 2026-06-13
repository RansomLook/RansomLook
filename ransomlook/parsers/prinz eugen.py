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

                shells = soup.find_all("a", class_="landing-shell--portal")
                for shell in shells:
                    h2 = shell.find("h2", class_="landing-portal-frame__name")
                    title = h2.get_text(strip=True) if h2 else ""
                    if not title:
                        continue

                    desc_el = shell.find("p", class_="landing-portal-frame__desc")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    link = shell.get("href", "")

                    entry = {"title": title, "description": description}
                    if link:
                        entry["link"] = link
                        entry["slug"] = filename
                    list_div.append(entry)

        except Exception:
            logger.debug("Failed during: " + filename)

    logger.debug(list_div)
    return list_div
