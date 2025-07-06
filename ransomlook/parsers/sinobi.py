import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name=soup.find_all('div', {"class": "news__block chat__block"})
                for div in divs_name:
                    title = div.find('h4').text.strip()
                    description = div.find('p',{"class" : "chat__block-descr"}).text.strip()
                    list_div.append({"title" : title, "description" : description, "link" : div.a['href'], "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
