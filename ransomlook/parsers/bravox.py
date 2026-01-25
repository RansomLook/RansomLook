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
                divs_name=soup.find_all('div', {"class": "flex flex-1 flex-col space-y-4 p-6"})
                for div in divs_name:
                    try:
                        title = div.find('h3').text.strip()
                    except:
                        continue
                    try:
                        description = div.find('p').text.strip()
                    except:
                        description = ""
                    link = div.find('a')["href"]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})

                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
