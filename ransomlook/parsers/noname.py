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
                divs_name=soup.find_all('article', {"class": "uagb-post__inner-wrap"})
                for div in divs_name:
                    title = div.find('h4').text.strip()
                    description = list(div.find('div',{"class" : "uagb-post__text uagb-post__excerpt"}).stripped_strings)[-1]
                    list_div.append({"title" : title, "description" : description, "link" : div.h4.a['href'], "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
