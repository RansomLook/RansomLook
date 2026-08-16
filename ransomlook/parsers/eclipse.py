import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r', encoding='utf-8')
                soup=BeautifulSoup(file,'html.parser')
                divs_name=soup.find_all('a', {"class": "leak-item"})
                for div in divs_name:
                    title = div.find('h2',{"class": "card-title"}).text.strip()
                    try:
                        description = div.find('div',{"class": "preview-text"}).text.strip()
                    except:
                        description = ''
                        pass
                    link = div['href']
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()
        except Exception as e:
            print("Error in parsing file: " + filename + " | " + str(e))
            pass
    print(list_div)
    return list_div
