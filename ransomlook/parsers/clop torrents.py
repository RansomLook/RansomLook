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
                tbody = soup.find('tbody')
                divs_name = tbody.find_all('tr') # type: ignore
                for div in divs_name:
                    tds = div.find_all('td')
                    title = tds[0].text.strip()
                    description = tds[2].text.strip()
                    magnets = tds[2].find_all('span',{'class', 'magnet_link'})
                    for magnet in magnets:
                        list_div.append({"title" : title, "description" : description, "magnet": magnet.text.strip()})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
