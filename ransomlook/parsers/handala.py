import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]
    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            try:
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name = soup.find_all('li',{"class":"wp-block-post"})
                for div in divs_name:
                    meta = div.find('a')
                    title = meta.text.strip()
                    description = div.find('div',{"class":"wp-block-post-excerpt"}).text.strip()
                    link = meta["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
            except:
                pass
    print(list_div)
    return list_div
