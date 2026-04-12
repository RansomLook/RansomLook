import os
import re

from bs4 import BeautifulSoup

def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                for card in soup.find_all("div", {"class": "card"}):
                    title_tag = card.find("div", {"class": "title"})
                    if title_tag is None:
                        continue
                    if "[ COOPERATION REACHED ]" in title_tag.get_text(strip=True):
                        continue
                    title = "AUDIT ENTITY: " + title_tag.get_text(strip=True)
                    resolved = card.find_all("div", {"class": "resolved-info"})
                    meta = card.find_all("div", {"class": "meta-info"})
                    if resolved:
                        description = " / ".join(r.get_text(strip=True) for r in resolved)
                    else:
                        description = " / ".join(m.get_text(strip=True) for m in meta)
                    link = ""
                    onclick = card.get("onclick", "")
                    match = re.search(r"'([^']+)'", onclick)
                    if match:
                        link = match.group(1)
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            print("Failed during : " + filename)
    print(list_div)
    return list_div
