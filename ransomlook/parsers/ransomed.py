import os
from bs4 import BeautifulSoup

def main():
    list_div=[]
    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                print(filename)
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                div = soup.find('div')
                divs_name=div.find_all('a', {"style":"margin-bottom: 10px; color: #ccc; font-family: monospace; text-decoration: underline; cursor: pointer;"}) # type: ignore
                for a in divs_name:
                    list_div.append(a.text.strip())
                file.close()
        except:
            pass
    print(list_div)
    list_div = list(dict.fromkeys(list_div))
    return list_div
