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
            divs_name=soup.find_all('div', {"class": "target-container"})
            for div in divs_name:
                title = div.find('div', {"class": "target-title"}).text.split('|')[0].strip()
                description = div.find_all('p')[0].text.strip()
                try:
                    link = div.find('a', {"class": "download-btn"})['href']
                    list_div.append({'title' : title, 'description': description, 'link': link, 'slug': filename})
                except:
                    list_div.append({'title' : title, 'description': description})
            file.close()
    print(list_div)
    return list_div
