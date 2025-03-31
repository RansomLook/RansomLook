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
                divs_name=soup.find_all('div', {"class": "w-full rounded-lg max-w-md bg-gray-900"})
                for div in divs_name:
                    title = div.find('a').text.strip()
                    description = div.find('div',{"class": "whitespace-pre-line break-words"}).text.strip()
                    link = div.find('a')['href']
                    list_div.append({'title':title, 'description': description, 'link': link, 'slug': filename})
                file.close()

        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
