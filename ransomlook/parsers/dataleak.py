import os
from bs4 import BeautifulSoup # type: ignore
import bs4

def main():
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name=soup.find_all('entry')
                for div in divs_name:
                    title = div.find(text=lambda tag: isinstance(tag, bs4.CData)).string.strip()
                    print(title)
                    desc = BeautifulSoup(div.contents[9].find(text=lambda tag: isinstance(tag, bs4.CData)).string.strip(),'html.parser')
                    description = desc.p.text.strip()
                    list_div.append({'title':title, 'description': description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
