import os
from bs4 import BeautifulSoup
from typing import Dict, List
import json

def main() -> List[Dict[str, str]] :
    list_div=[]
    list_api=[]
    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                if 'api' in filename:
                    jsonpart= soup.pre.contents # type: ignore
                    data = json.loads(jsonpart[0]) # type: ignore
                    for entry in data['data']['leaks']:
                        title =  entry['title']
                        description = entry['descryption'].strip()
                        link = '/leak/'+entry['rndid']
                        list_api.append({"title" : title, "description" : description, "link": link, "slug": filename})
                else:
                    div=soup.find('div', {"class": "grid"})
                    divs_name = div.find_all('a') # type: ignore
                    for div in divs_name:
                        title = div.find('div', {"class": "grid-caption__title"}).contents[0].strip()
                        description = ''
                        link = div['href']
                        list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    for item in list_div:
        for apiitem in list_api:
            if item['title'] == apiitem['title']:
               item['description'] = apiitem['description']
               break
    print(list_div)
    return list_div
