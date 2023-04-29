import os
from bs4 import BeautifulSoup
import json

def main():
    list_div=[]
    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            print(filename)
            file=open(html_doc,'r')
            soup=BeautifulSoup(file,'html.parser')
            if 'onion-n' in filename:
                jsonpart= soup.pre.contents # type: ignore
                data = json.loads(jsonpart[0]) # type: ignore
                for entry in data:
                    title = entry['title'].strip()
                    description = entry['content'].strip()
                    list_div.append({"title" : title, "description" : description})
            file.close()
    print(list_div)
    return list_div
