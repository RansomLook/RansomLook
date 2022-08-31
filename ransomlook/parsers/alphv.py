import os
from bs4 import BeautifulSoup # type: ignore
import json

def main():
    list_div=[]
    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                if 'api' in filename:
                    jsonpart= soup.pre.contents
                    data = json.loads(jsonpart[0])
                    for entry in data['items']:
                       list_div.append(entry['title'].strip())
                else :
                    divs_name=soup.find_all('div',{'class': 'post-header'})
                    for div in divs_name:
                        for item in div.contents :
                            list_div.append(item.text.strip())
                file.close()
        except:
            pass
    list_div = list(dict.fromkeys(list_div))
    print(list_div)

    return list_div
