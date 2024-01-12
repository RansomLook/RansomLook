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
            divs_name=soup.find_all('div', {"class": "title is-4"})
            for div in divs_name:
                list_div.append(div.a.text.strip())
            file.close()
    list_div = list(dict.fromkeys(list_div))
    print(list_div)
    return list_div
