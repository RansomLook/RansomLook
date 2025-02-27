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
            divs_name=soup.find_all('div', {"class": "card h-100"})
            for div in divs_name:
                title = div.find('h5').text.strip()
                description = div.find('p').text.strip()
                link = div.a['href']
                list_div.append({'title' : title, 'description': description, 'link': link, 'slug': filename})
            file.close()
    print(list_div)
    return list_div
