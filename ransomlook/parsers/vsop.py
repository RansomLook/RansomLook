import os
from bs4 import BeautifulSoup # type: ignore

def main():
    list_div=[]

    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            file=open(html_doc,'r')
            soup=BeautifulSoup(file,'html.parser')
            divs_name=soup.find_all('h6', {"class": "uppercase font-x1"})
            for div in divs_name:
                list_div.append(div.text.strip())
            divs_name=soup.find_all('h6', {"class": "nospace uppercase font-x1"})
            for div in divs_name:
                list_div.append(div.text.strip())
            file.close()
    list_div = list(dict.fromkeys(list_div))
    print(list_div)
    return list_div
