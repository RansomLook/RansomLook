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
                if '-data' in filename:
                    jsonpart= soup.pre.contents # type: ignore
                    print(jsonpart)
                    data = json.loads(jsonpart[0]) # type: ignore
                    print(data)
                    for entry in data:
                        title = entry['company']
                        description = entry['comment']
                        list_div.append({'title':title, 'description': description})
                else :
                    body=soup.find('tbody')
                    if body != None:
                        divs_name=body.find_all('tr') # type: ignore
                        for div in divs_name:
                            tds = div.find_all('td')
                            title = tds[1].text.strip()
                            description =  ''
                            list_div.append({'title':title, 'description': description})
                    divs_name=soup.find_all('div', {"class": "ant-card css-ut69n1"})
                    for div in divs_name:
                        title = div.find('h2').text.strip()
                        description=''
                        list_div.append({'title':title, 'description': description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
