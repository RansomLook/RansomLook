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
                if 'api-blog-get' in filename:
                    jsonpart= soup.pre.contents # type: ignore
                    data = json.loads(jsonpart[0]) # type: ignore
                    for entry in data:
                        title = entry['comname'].strip()
                        description = entry['descr'].strip()
                        link= str(entry['_id'])
                        list_div.append({"title" : title, "description" : description, "link": '/#/post/'+link, "slug": filename})
                else:
                    divs_name=soup.find_all('div', {'class': 'p-4 border-1 surface-border surface-card border-round gap-1'})
                    for div in divs_name:
                        title = div.find('div', {'class': 'text-2xl font-bold'}).text.strip()
                        description = div.find('div', {'class': 'blog-preview'}).text.strip()
                        div2 = div.find('div', {'class': 'post-footer-right'})
                        list_div.append({'title':title, 'description': description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)

    return list_div
