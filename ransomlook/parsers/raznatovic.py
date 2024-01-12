import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]
    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            try:
                html_doc='source/'+filename
                print(filename)
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name = soup.find_all('div',{"class":"card"})
                for div in divs_name:
                    if 'id' in div:
                        continue
                    title = div.b.u.text.strip()
                    description = div.find('ul').text.strip()
                    link = div.find('a')['href']
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                file.close()
            except:
                pass
    print(list_div)
    return list_div
