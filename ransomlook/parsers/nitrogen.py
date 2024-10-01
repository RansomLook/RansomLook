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
                divs_name=soup.find_all('div', {"class": "w3-container"})
                for div in divs_name:
                    title = div.find('h3').text.strip()
                    description = div.find_all('p')[1].text.strip()
                    link = div.find('a',{"class":"w3-button w3-padding-large w3-white w3-border"})['href']
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
