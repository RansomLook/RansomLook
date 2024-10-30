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
            ls = soup.find('ls')
            if ls is not None:
                divs_name=ls.find_all('a') # type: ignore
                for div in divs_name:
                  try:
                    title = div.find('span').text.strip()
                    description = div.find('url').text.strip()
                    link = div['href']
                    list_div.append({'title': title, 'description': description, 'link': link, 'slug': filename})
                  except:
                    pass
            file.close()
    print(list_div)
    return list_div
