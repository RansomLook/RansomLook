import os
from urllib.parse import quote

from bs4 import BeautifulSoup


def main():
    """
    Parser for the Exitium ransomware DLS.

    Victims are rendered server-side as div.target-card elements inside
    #targetGrid. Two states:
    - .pending: countdown active, not yet published
    - .clickable-card: published, has data-zip download link

    Data is in the HTML directly (h3.target-title, p.target-text,
    data-publish-date, data-zip attributes).
    """
    list_posts = []
    parser_name = __name__.split('.')[-1]  # 'exitium'

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

        grid = soup.find('div', id='targetGrid')
        if not grid:
            continue

        for card in grid.find_all('div', class_='target-card'):
            title_tag = card.find('h3', class_='target-title')
            if not title_tag:
                continue
            name = title_tag.get_text(strip=True)
            # Remove the crosshairs icon text if present
            for icon in title_tag.find_all('i'):
                icon.decompose()
            name = title_tag.get_text(strip=True)
            if not name:
                continue

            post = {
                'title': name,
                'slug': filename,
                'link': '#' + quote(name),
            }

            # Description
            desc_tag = card.find('p', class_='target-text')
            if desc_tag:
                post['description'] = desc_tag.get_text(strip=True)

            list_posts.append(post)

    return list_posts
