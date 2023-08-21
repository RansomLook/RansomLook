import os
from bs4 import BeautifulSoup

def main():
    list_div=[]
    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            print(filename)
            file=open(html_doc,'r')
            soup=BeautifulSoup(file,'html.parser')
            div = soup.find('div',{"class":"di"})
            divs_name=div.find_all('a') # type: ignore
            for a in divs_name:
                if a.text.strip() != "{Censored}":
                    list_div.append(a.text.strip().replace('{','').replace('}',''))
            file.close()
    print(list_div)
    list_div = list(dict.fromkeys(list_div))
    return list_div
