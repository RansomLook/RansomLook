import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]
    blacklist=['HOME', 'HOW TO DOWNLOAD?', 'ARCHIVE']
    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            print(filename)
            file=open(html_doc,'r')
            soup=BeautifulSoup(file,'html.parser')
            divs_name=soup.find_all('span', {"class": "g-menu-item-title"})
            for div in divs_name:
                for item in div.contents :
                    if item in blacklist:
                       continue
                    list_div.append(item.text.strip())
            file.close()
    print(list_div)
    list_div = list(dict.fromkeys(list_div))
    return list_div
