import os
from bs4 import BeautifulSoup # type: ignore

def main():
    list_div=[]

    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            file=open(html_doc,'r')
            soup=BeautifulSoup(file,'html.parser')
            divs_name=soup.find_all('div', {"class": "card-header d-flex justify-content-between"})
            for div in divs_name:
                itemize= div.find_all('h2')
                for item in itemize :
                    list_div.append(item.text.strip())
            file.close()
    list_div = list(dict.fromkeys(list_div))
    print(list_div)
    list_div=[]
    return list_div
