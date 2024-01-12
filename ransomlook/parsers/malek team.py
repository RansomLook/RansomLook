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
                divs_name=soup.find_all('div', {"class": "timeline_item"})
                for div in divs_name:
                    title = div.find('div', {"class":"timeline_date-text"}).text
                    print(title)
                    try:
                        description = div.find("div", {"class": "margin-bottom-medium"}).text.strip()
                    except:
                        description = div.find("div", {"class": "margin-bottom-xlarge"}).text.strip()
                    print(description)
                    try:
                        link = div.find('a', {"class":"btn btn-danger"})['href']
                        list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                    except:
                        list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
