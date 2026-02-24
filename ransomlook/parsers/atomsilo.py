import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]

    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            file=open(html_doc,'r')
            soup=BeautifulSoup(file,'html.parser')
            ### old template
            divs_name=soup.find_all('h4', {"class": "post-announce-name"})

            for div in divs_name:
                for item in div.contents[1]:
                    list_div.append(item.text.strip())
            ###

            divs_name=soup.find_all('div', {"class": "leak-card"})

            for div in divs_name:
                title =  div.find('h3').text.strip()
                descriptions =div.find_all('li')
                description = " ".join(li.get_text(strip=True) for li in descriptions)
                link = div.find('a')["href"]
                list_div.append({"title": title, "description": description.strip(), "link": link, "slug": filename})

            file.close()

    print(list_div)
    return list_div
