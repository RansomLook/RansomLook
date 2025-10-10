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
            divs = soup.find_all('div',{"class": "flex flex-col w-full h-[200px] p-[15px] gap-2.5 rounded-[10px] border backdrop-blur-[15px] bg-[rgba(103,66,66,0.35)] border-[rgba(103,66,66,0.12)]"})
            for div in divs:
                try:
                    title = div.find('span').text.strip()
                    description = div.find('div',{"class": "flex-1 w-full overflow-hidden text-white text-xs leading-[130%] font-normal whitespace-nowrap text-ellipsis"}).text.strip()
                    list_div.append({'title': title, 'description': description})
                except:
                    continue
            divs = soup.find_all('div',{"class": "flex flex-col w-full h-[200px] p-[15px] gap-2.5 rounded-[10px] border backdrop-blur-[15px] bg-[rgba(66,103,66,0.35)] border-[rgba(66,103,66,0.12)]"})
            for div in divs:
                try:
                    title = div.find('span').text.strip()
                    print(title)
                    description = div.find('div',{"class": "flex-1 w-full overflow-hidden text-white text-xs leading-[130%] font-normal whitespace-nowrap text-ellipsis"}).text.strip()
                    list_div.append({'title': title, 'description': description})
                except:
                    continue

            file.close()
    print(list_div)
    return list_div
