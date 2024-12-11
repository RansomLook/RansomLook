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
                divs_name=soup.find_all('center')
                for div in divs_name:
                    try:
                        title = div.find('p', {"class": "h1"}).text
                        description = div.find("p", {"class": "description"}).text.strip()
                        list_div.append({"title" : title, "description" : description})
                    except:
                        pass
                divs_name=soup.find_all('div', {"class": "item-details"})
                for div in divs_name:
                    try:
                        title = div.find('h3').text
                        description = div.find("p").text.strip()
                        list_div.append({"title" : title, "description" : description})
                    except:
                        pass
                divs_name =  soup.find('table',{"class":"data-table table nowrap"}) # type: ignore
                try:
                    divs = divs_name.find_all('tbody') # type: ignore
                    for div in divs:
                        title = div.find('div',{"class":"txt"}).text.strip()
                        description = ''
                        list_div.append({"title" : title, "description" : description})
                except:
                    pass
                divs_name=soup.find_all('div', {"class": "post-card"})
                for div in divs_name:
                    try:
                        title = div.find('h4').text.strip()
                        description = div.find('p', {"class": "subtitle"}).text.strip()
                        list_div.append({'title': title, 'description': description})
                    except:
                        pass
                file.close()

        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
