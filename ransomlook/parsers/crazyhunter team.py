import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]

    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            file=open(html_doc,'r')
            soup=BeautifulSoup(file,'html.parser')
            divs_name=soup.find_all('div', {"data-slot": "card"})
            for div in divs_name:
                title = div.find('h3').text.strip()
                description = ''
                try:
                    link = div.find('a')['href']
                    list_div.append({'title' : title, 'description': description, 'link': link, 'slug': filename})

                except:
                    list_div.append({'title' : title, 'description': description})
            file.close()
    print(list_div)
    return list_div
