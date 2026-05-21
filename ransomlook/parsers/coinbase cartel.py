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
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                for feat in soup.find_all("div", {"class": "featured"}):
                    name = feat.find("span", {"class": "featured-name"})
                    title = name.text.strip() if name else ""
                    tags = [t.text.strip() for t in feat.find_all("span", {"class": "featured-tag"})
                            if "status" not in t.get("class", []) and t.text.strip()]
                    description = " - ".join(tags)
                    link_tag = feat.find("a", {"class": "primary"}, href=True) or feat.find("a", href=True)
                    link = link_tag["href"] if link_tag else ""
                    if title:
                        list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                divs_name = soup.find_all("div", {"class": "target-row"})
                for div in divs_name:
                    name = div.find("span", {"class": "target-name"})
                    title = (name.text if name else div.get("data-name", "")).strip()
                    industry = div.find("span", {"class": "target-industry"})
                    rev = div.find("span", {"class": "target-rev"})
                    parts = [span.text.strip() for span in (industry, rev) if span and span.text.strip()]
                    description = " - ".join(parts)
                    link_tag = div.find("a", href=True)
                    link = link_tag["href"] if link_tag else ""
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            logger.debug("Failed during : " + filename)
    logger.debug(list_div)
    return list_div
