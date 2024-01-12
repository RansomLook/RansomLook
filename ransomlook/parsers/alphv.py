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
                if 'api' in filename:
                    jsonpart= soup.pre.contents # type: ignore
                    data = json.loads(jsonpart[0]) # type: ignore
                    for entry in data['items']:
                        title = entry['title'].strip()
                        description = entry['publication']['description'].strip()
                        link = '/'+entry['id']
                        list_div.append({'title':title, 'description': description, 'link': link, 'slug': filename})
                else :
                    divs_name=soup.find_all('div', {'class': 'post'})
                    for div in divs_name:
                        title = div.find('div', {'class': 'post-header'}).text.strip()
                        description = div.find('div', {'class': 'post-description'}).text.strip()
                        print(description)
                        div2 = div.find('div', {'class': 'post-footer-right'})
                        link = div2.find('a')["href"]
                        list_div.append({'title':title, 'description': description, "link": link, "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)

    return list_div
