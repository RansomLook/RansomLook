import os
from bs4 import BeautifulSoup
from typing import Dict, List
import json

def main() -> List[Dict[str, str]] :
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name=soup.find_all('div',{"class":"card"})
                for div in divs_name:
                    title = div.find('div',{"class": "card-title"}).text.strip()
                    description = div.find('div', {"class": "card-desc"}).text.strip()
                    list_div.append({'title':title, 'description': description})
                try:
                    jsonpart= soup.pre.contents # type: ignore
                    data = json.loads(jsonpart[0]) # type: ignore
                    for entry in data:
                        title =  entry['title']
                        description = entry['description'].strip()
                        list_div.append({"title" : title, "description" : description})
                except:
                    pass
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
