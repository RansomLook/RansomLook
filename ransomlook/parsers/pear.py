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
            
            divs_name=soup.find_all('td',{"class": "es-text-7589"})
            for div in divs_name:
                title = div.find('strong').find(string=True, recursive=False).strip()
                description = div.find_all('p')[1].text.strip()
                link =  div.find_all('a')[1]['href']
                list_div.append({'title': title, 'description': description, "link": link, "slug": filename})
            file.close()
    print(list_div)
    return list_div
