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
                divs_name=soup.find_all('div', {"class": "card card-custom h-100 p-3 victim-card"})
                for div in divs_name:
                    title = div.find('h5').text.strip()
                    description = div.find('p', {"class": "card-text truncated-description"}).text.strip()
                    list_div.append({"title" : title, "description" : description})

                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
