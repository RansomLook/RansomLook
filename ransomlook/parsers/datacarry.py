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
                divs_name=soup.find_all('a', {"class": "icon"})
                for div in divs_name:
                    if div.has_attr('onclick'):
                        continue
                    try:
                        title = div.find('div').text.strip()
                        description = ""
                        list_div.append({"title" : title, "description" : description})
                    except:
                        pass

                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
