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
                divs_name=soup.find_all('div', {"class": "relative bg-white rounded-lg shadow dark:bg-gray-700"})
                for div in divs_name:
                    title = div.find('h3').text.strip().split('\n')[0].strip()
                    description = div.find('p', {'class':"break-all"}).text.strip()
                    list_div.append({"title" : title, "description" : description})
                divs_name=soup.find_all('div', {"class": "flex flex-col space-y-8"})
                for div in divs_name:
                    title = div.find('span', {"class": "text-5xl font-semibold"}).text.strip()
                    description = div.find('span', {'class':"text-xl font-normal"}).text.strip()
                    link = div.a['href']
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
