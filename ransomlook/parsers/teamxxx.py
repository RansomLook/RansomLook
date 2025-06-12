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
                divs_name=soup.find_all('div', {"class": "center1"})
                for div in divs_name:
                    title = div.find('div',{"id": "father"}).text.strip().replace(' ', '', 1)
                    description = div.find('p',{"id" : "TextColor"})
                    children = list(description.children)
                    last_i_index = max(i for i, child in enumerate(children) if child.name == 'i')
                    after_last_i = children[last_i_index + 1:]
                    description = ''.join(str(elem) for elem in after_last_i).strip()
                    list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
