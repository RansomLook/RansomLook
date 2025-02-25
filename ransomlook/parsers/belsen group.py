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
                divs_name=soup.find('table',{"class": "table table-striped custom-table"})
                tbody = divs_name.find('tbody') # type: ignore
                trs = tbody.find_all('tr') # type: ignore
                for div in trs:
                    try:
                        td = div.find_all('td')
                        title = td[0].text.strip()
                        try:
                            description = td[1].text.strip()
                        except:
                            description=''
                        list_div.append({"title" : title, "description" : description})
                    except:
                        pass
                file.close()

        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
