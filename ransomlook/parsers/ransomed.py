import os
from bs4 import BeautifulSoup

def main():
    list_div=[]
    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            try:
                html_doc='source/'+filename
                print(filename)
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                div = soup.find_all('div',{"style":"text-align: center;"})
                divs_name=div[2].find_all('a', {"style":"margin-bottom: 10px; color: #ccc; font-family: monospace; text-decoration: underline; cursor: pointer;"}) # type: ignore
                for a in divs_name:
                    list_div.append({"title": a.text.strip(), "description": "", "link": a['href'], "slug": filename})
                file.close()
            except:
                pass
    print(list_div)
    return list_div
