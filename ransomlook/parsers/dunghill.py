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
                divs = soup.find_all('div',{"class": "custom-container"})
                for div in divs:
                    title = div.find('div', {"class": "ibody_title"}).text.strip()
                    description = div.find("div", {"class": "ibody_body"}).find_all('p')
                    description = description[2].text.strip()
                    link = div.find('div', {"class": "ibody_ft_right"}).a['href']
                    list_div.append({"title" : title, "description" : description, 'link': link, 'slug': filename})
                divs = soup.find_all('div',{"class": "custom-container2"})
                for div in divs:
                    title = div.find('strong').text.strip()
                    description = div.find_all('p')
                    description = description[2].text.strip()
                    link = div.find('a')['href']
                    list_div.append({"title" : title, "description" : description, 'link': link, 'slug': filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
