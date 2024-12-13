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
                divs_name=soup.find_all('table')
                for div in divs_name:
                    try:
                        trs = div.find_all('tr')
                        title = trs[0].find_all('td')[1].text.strip()
                        try:
                            description = trs[5].find_all('td')[1].text.strip()
                        except:
                            description='To be announced...'
                        list_div.append({"title" : title, "description" : description})
                    except:
                        pass
                file.close()

        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
