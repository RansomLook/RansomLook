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
                divs_name=soup.find_all('div', {"class":"card text-white bg-dark m-2 card-danger"})
                for div in divs_name:
                    title = div.find('a').text.strip()
                    description = div.find('div', {"class":"card-body"}).text.strip()
                    link =  div.find('a')['href']
                    list_div.append({"title" : title, "description" : description, 'link': link, 'slug': filename})
                divs_name=soup.find_all('div', {"class":"card text-white bg-dark m-2 card-success"})
                for div in divs_name:
                    title = div.find('a').text.strip()
                    description = div.find('div', {"class":"card-body"}).text.strip()
                    link =  div.find('a')['href']
                    list_div.append({"title" : title, "description" : description, 'link': link, 'slug': filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
