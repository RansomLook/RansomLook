import json
import os

from bs4 import BeautifulSoup

def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                jsonpart = soup.pre.contents  # type: ignore
                data = json.loads(jsonpart[0])  # type: ignore
                for entry in data.get("posts", []):
                    title = entry.get("title", "").strip()
                    if not title:
                        continue
                    description = entry.get("short_desc", "").strip()
                    website = entry.get("website", "").strip()
                    if website:
                        description = f"{website} - {description}" if description else website
                    link = "/post/" + entry.get("id", "")
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            print("Failed during : " + filename)
    print(list_div)
    return list_div
