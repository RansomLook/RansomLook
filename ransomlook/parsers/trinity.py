import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]
    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            try:
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name = soup.find_all('div',{"class":"bg-secondary"})
                for div in divs_name:
                    article =  div.find('div')
                    para = article.find_all('p')
                    para[0].strong.decompose()
                    title= para[0].text.strip()
                    para[1].strong.decompose()
                    description = para[1].text.strip()
                    link = div.find('a')["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})
                divs_name = soup.find_all('div',{"class":"card-body"})
                for div in divs_name:
                    title= div.find('h5').text.strip()
                    description = div.find('p',{"class": "card-text"}).text.strip()
                    link = div.find('a')["href"]
                    list_div.append({"title": title, "description": description, "link": link, "slug": filename})

                file.close()
            except:
                pass
    print(list_div)
    return list_div
