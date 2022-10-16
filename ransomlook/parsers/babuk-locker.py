import os
from bs4 import BeautifulSoup # type: ignore

def main():
    list_div=[]

    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            file=open(html_doc,'r')
            soup=BeautifulSoup(file,'html.parser')
            divs_name=soup.find_all('div', {"class": "col-lg-4 col-sm-6 mb-4"})
            for div in divs_name:
                itemize= div.find_all('h5')
                for item in itemize :
                    list_div.append(item.text.strip())
            file.close()
    list_div = list(dict.fromkeys(list_div))
    return list_div
