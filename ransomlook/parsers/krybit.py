import os

from bs4 import BeautifulSoup

from ransomlook.default.logging import get_logger

def main() -> list[dict[str, str]]:
    list_div = []

    for filename in os.listdir("source"):
        try:
            if filename.startswith(__name__.split(".")[-1] + "-"):
                html_doc = "source/" + filename
                file = open(html_doc, encoding="utf-8")
                soup = BeautifulSoup(file, "html.parser")
                for card in soup.find_all("div", {"class": "post-card"}):
                    title = card.find('h3').text.strip()
                    description = card.find("div", {"class": "post-excerpt"}).text.strip()
                    link = card['onclick'].split("'")[1]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
        except Exception:
            print("Failed during : " + filename)
    print(list_div)
    return list_div
