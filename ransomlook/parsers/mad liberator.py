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
                divs_name=soup.find_all('div', {"class": "col-md-6"})
                for div in divs_name:
                    sec = div.find('div',{"class":"blog-list--desc p-3 cnt"})
                    title = sec.find('h3').text.strip()
                    description = sec.find('p').text.strip()
                    try :
                        link = div.find('a')['href']
                        list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                    except:
                        list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
