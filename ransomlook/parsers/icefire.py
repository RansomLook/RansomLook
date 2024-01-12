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
            #divs_name=soup.find_all('th', {"class": "align-middle", "style":"height:63px"})
            divs_name=soup.find_all('tr', {"class": "fw-normal"})
            for div in divs_name:
                for item in div.find('td').contents :
                    if item.text.strip() == '':
                        continue
                    list_div.append(item.text.strip())
            file.close()
    list_div = list(dict.fromkeys(list_div))
    if 'updating' in list_div:
        list_div.remove('updating')
    print(list_div)
    return list_div
