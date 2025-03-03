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
            divs_name=soup.find_all('div', {"class": "incident-info"})
            for div in divs_name:
                print(div)
                data = div.find_all('dd')
                title = data[0].text.strip()
                description = data[1].text.strip()
                list_div.append({'title' : title, 'description': description})
            file.close()
    print(list_div)
    return list_div
