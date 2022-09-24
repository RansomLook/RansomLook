import os
from bs4 import BeautifulSoup # type: ignore

def main():
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name=soup.find_all('article', {"class": "ciz-post"})
                for div in divs_name:
                    title = div.h3.a.text.strip()
                    description = div.find('div', {'class': 'post-des'}).p.text.strip()
                    list_div.append({'title':title, 'description': description})
                divs_name=soup.find_all('div', {"class": "category-mid-post-two"})
                for div in divs_name:
                    title = div.h2.a.text.strip()
                    description = div.find('div', {'class': 'post-des dropcap'}).p.text.strip()
                    list_div.append({'title':title, 'description': description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
