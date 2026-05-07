import json
import os
import re
from urllib.parse import quote

from bs4 import BeautifulSoup


def main() -> list[dict[str, str]]:
    """
    Parser for the Icarus ransomware DLS.

    The HTML is server-side rendered: #victims-list contains
    div.victim-item cards with data-victim-id / data-name / data-desc
    attributes and an inner <h4> with the victim name.

    A <script> block also defines `var victimsData = [...]` which holds
    the full JSON record per victim (countdown_end, data_stolen,
    download_link, photos, size_gb). We use it to enrich the post date
    when present, and fall back to HTML scraping otherwise.

    Screenshots: link is '#VictimName' — an init_script can read
    location.hash and click the matching card to open the detail panel.
    """
    list_posts = []
    parser_name = __name__.split('.')[-1]  # 'icarus'

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

        # Build an id -> json record lookup from the embedded JS.
        victims_json = {}
        m = re.search(r'var\s+victimsData\s*=\s*(\[.*?\])\s*;', content, re.DOTALL)
        if m:
            try:
                for v in json.loads(m.group(1)):
                    if 'id' in v:
                        victims_json[v['id']] = v
            except Exception:
                pass

        for item in victims_container.find_all('div', class_='victim-item'): # type: ignore[union-attr]
            h4 = item.find('h4')
            if not h4:
                continue
            name = h4.get_text(strip=True)
            if not name:
                continue

            post = {
                'title': name,
                'slug': filename,
                'link': '#' + quote(name),
            }

            desc_tag = item.find('p', class_='victim-desc')
            if desc_tag:
                post['description'] = desc_tag.get_text(strip=True)

            list_posts.append(post)

    return list_posts
