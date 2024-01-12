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
                divs_name=soup.find_all('div', {"class": "bg-cover border-rounded mb-3"})
                for div in divs_name:
                    title = div.find('h2', {"title": "Company name"}).text.strip()
                    description = div.find('div',{"class" : "fs-5"}).text.strip()
                    list_div.append({"title" : title, "description" : description})
                divs_name=soup.find_all('div', {"class": "col-lg-4 my-3 d-flex flex-column justify-content-between"})
                for div in divs_name:
                    title = div.find('h2', {"title": "Company name"}).text.strip()
                    description = div.find('div',{"class" : "mb-2 text-justify"}).text.strip()
                    link = div.find('div',{"class": "d-flex align-items-center justify-content-between"}).a["href"]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                divs_name=soup.find_all('div', {"class": "d-flex flex-column justify-content-between flex-fill"})
                for div in divs_name:
                    title = div.find('h2', {"title": "Company name"}).text.strip()
                    description = div.find('small',{"class" : "text-justify"}).text.strip()
                    link = div.find('a',{"class": "btn btn-sm btn-primary h2 mb-0"})["href"]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
