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
                divs_name=soup.find_all('div',{"class":"segment__contant"})
                for div in divs_name:
                    title = div.find('div',{"class":"segment__text__off"}).text.strip()
                    try:
                        description = div.find('div',{"class":"segment__text__dsc"}).text.strip()
                    except:
                        description = ''
                        pass
                    try:
                        link = div.parent['onclick'].split("'")[1]
                        list_div.append({"title" : title, "description" : description, 'link': link, 'slug': filename})
                    except:
                        list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
