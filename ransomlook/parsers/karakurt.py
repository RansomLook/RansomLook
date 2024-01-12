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
                prereleases = soup.find('div', {"id": "companies_prereleases"})
                divs_name = prereleases.find_all('div', {"class": "col-md-4 col-sm-4 col-xs-12"}) # type: ignore
                for div in divs_name:
                    h3 = div.find('h3')
                    title = h3.text.strip()
                    description = div.find('div', {'class': 'post-des'}).p.text.strip()
                    link = h3.a['href']
                    list_div.append({'title':title, 'description': description, 'link': link, 'slug': filename})
                divs_name=soup.find_all('div', {"class": "col-xs-6 col-md-3 col-sm-3"})
                for div in divs_name:
                    title = div.h3.a.text.strip()
                    description = div.find('div', {'class': 'post-des'}).text.strip()
                    print(description)
                    link = div.h3.a['href']
                    list_div.append({'title':title, 'description': description, 'link': link, 'slug': filename})
                divs_name=soup.find_all('div', {"class": "category-mid-post-two"})
                for div in divs_name:
                    title = div.h2.a.text.strip()
                    description = div.find('div', {'class': 'post-des dropcap'}).p.text.strip()
                    link = div.h2.a['href']
                    list_div.append({'title':title, 'description': description, 'link': link, 'slug': filename})
                file.close()
        except:
            
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
