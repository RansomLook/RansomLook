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
                divs_name=soup.find_all('div', {"class": "block relative p-8 bg-gray-800 rounded-lg transition duration-300 ease-in-out"})
                for div in divs_name:
                    title = div.find('h2').text.strip()
                    description = div.find('p').text.strip()
                    a = div.find_all('a')
                    try:
                        link = a[1]['href']
                        list_div.append({"title" : title, "description" : description, "link" : link, "slug": filename})
                    except:
                        list_div.append({"title" : title, "description" : description})
                        pass
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
