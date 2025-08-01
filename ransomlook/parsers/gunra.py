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
                divs_name=soup.find_all('div', {"style": "padding: 10px; margin-bottom: 10px; border-radius: 5px; background-color: azure;"})
                for div in divs_name:
                    title = div.find('h2').text.strip()
                    description = div.find('div', {"class": "industry"}).text.strip()
                    link = div.find('a')["href"]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                divs_name=soup.find_all('div', {"class": "tile"})
                for div in divs_name:
                    title =  div.find('a').text.strip()
                    description = div.find_all('div')[1].text.strip()
                    link = div.find('a')["href"]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()

        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
