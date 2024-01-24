
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
                divs_name=soup.find_all('div', {"class": "news_div"})
                for div in divs_name:
                    title = div.find('a').text.strip()
                    description = div.find('div',{"style" : "line-height:20px; padding-top:5px; margin-bottom:30px;"}).text.strip()
                    list_div.append({"title" : title, "description" : description, "link" : div.a['href'], "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
