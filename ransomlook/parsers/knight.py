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
                divs_name=soup.find_all('div', {"class": "card-body p-3 pt-2"})
                for div in divs_name:
                    a = div.find('a',{"class":"h5"})
                    title = a.text.strip()
                    description = div.find("p").text.strip()
                    link = a['href']
                    list_div.append({"title" : title, "description" : description, 'link': link, 'slug': filename})
                divs_name=soup.find_all('div', {"class": "card-body"})
                for div in divs_name:
                    try: 
                        h2 = div.find('h2',{"class":"card-title"})
                        title = h2.text.strip()
                        description = div.find("p").text.strip()
                        link = h2.a['href']
                        list_div.append({"title" : title, "description" : description, 'link': link, 'slug': filename})
                    except:
                        pass

                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
