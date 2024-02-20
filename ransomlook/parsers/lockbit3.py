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
                divs_name=soup.find_all('div', {"class": "post-block bad"})
                for div in divs_name:
                    title = div.find('div',{"class": "post-title"}).text.strip()
                    description = div.find('div',{"class" : "post-block-text"}).text.strip()
                    link = div['onclick'].split("'")[1]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                divs_name=soup.find_all('div', {"class": "post-block good"})
                for div in divs_name:
                    title = div.find('div',{"class": "post-title"}).text.strip()
                    description = div.find('div',{"class" : "post-block-text"}).text.strip()
                    link = div['onclick'].split("'")[1]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                divs_name=soup.find_all('a', {"class": "post-block bad"})
                for div in divs_name:
                    title = div.find('div',{"class": "post-title"}).text.strip()
                    description = div.find('div',{"class" : "post-block-text"}).text.strip()
                    link = div['href']
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                divs_name=soup.find_all('a', {"class": "post-block good"})
                for div in divs_name:
                    title = div.find('div',{"class": "post-title"}).text.strip()
                    try:
                        description = div.find('div',{"class" : "post-block-text"}).text.strip()
                    except:
                        description = ''
                    link = div['href']
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
