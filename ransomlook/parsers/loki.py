import os
from urllib.parse import quote

from bs4 import BeautifulSoup


def main():
    """
    Parser for the Loki ransomware DLS.

    Playwright renders the JS which populates #victims-list with
    div.victim-item elements containing <h4> victim names.

    Screenshots: link is '#VictimName' — the init_script reads
    location.hash, clicks the matching card, and opens the modal.
    """
    list_posts = []
    parser_name = __name__.split('.')[-1]  # 'loki'

    for filename in os.listdir('source'):
        if not filename.startswith(parser_name + '-'):
            continue
        filepath = os.path.join('source', filename)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            continue

        soup = BeautifulSoup(content, 'html.parser')

        victims_container = soup.find('div', id='victims-list')
        if not victims_container:
            continue

        for item in victims_container.find_all('div', class_='victim-item'):
            h4 = item.find('h4')
            if not h4:
                continue
            name = h4.get_text(strip=True)
            if name:
                list_posts.append({
                    'title': name,
                    'description': "",
                    'slug': filename,
                    'link': '#' + quote(name),
                })

    return list_posts
