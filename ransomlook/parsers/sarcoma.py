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
                divs_name=soup.find_all('div', {"class": "modal fade"})
                try:
                  for div in divs_name:
                    title = div.find('h5').text.strip()
                    description = div.find('pre',{"class":"text-break mb-2"}).text.strip()
                    try:
                        link = div.find('a')["href"]
                        if not link.startswith('http'):
                            link = 'http://'+link
                        list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                    except:
                        list_div.append({"title" : title, "description" : description})
                except:
                  pass
                divs_name=soup.find_all('div', {"class": "col"})
                for div in divs_name:
                    title = str(div.find('div',{"class":"card-title"}).text.strip().split('\t')[-1])
                    description = div.find('div',{"class":"card-text"}).text.strip()
                    try:
                        link = div.find('a')["href"]
                        if not link.startswith('http'):
                            link = 'http://'+link
                        list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                    except:
                        list_div.append({"title" : title, "description" : description})

                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
