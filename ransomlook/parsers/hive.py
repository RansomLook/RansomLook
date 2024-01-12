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
                if 'disclosed' in filename:
                    jsonpart= soup.pre.contents # type: ignore
                    data = json.loads(jsonpart[0]) # type: ignore
                    for entry in data:
                       list_div.append({"title":entry['title'].strip(),"description":entry["description"].strip()})
                else:
                    divs_name=soup.find_all('div', {"class": "blog-card-info"})
                    for div in divs_name:
                        title=div.h2.text.strip()
                        if div.p is not None:
                            description=div.p.text.strip()
                        else:
                            description = None
                        list_div.append({'title':title, 'description': description})
                file.close()
        except:
            pass
    print(list_div)
    return list_div
