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
                try:
                    header = soup.find('div',{"style":"display: grid; position: relative; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; padding-top: 16px; padding-bottom: 4px;"})
                    divs_name=header.find_all('div', {"class": "notion-selectable notion-page-block notion-collection-item"}) # type: ignore
                    for div in divs_name:
                        title = div.find('div',{"style":"width: 100%; display: flex; padding: 8px 10px 6px; position: relative;"}).text.strip()
                        description = div.find('div',{"style" : "padding-top: 0px; padding-bottom: 10px;"}).text.strip()
                        list_div.append({"title" : title, "description" : description, "link" : div.a['href'], "slug": filename})
                except:
                    pass
                divs_name = soup.find_all('div', {"style": "display: grid;    grid-template-columns: 200px 1fr;    grid-template-rows: auto auto auto 1fr auto;    gap: 10px;"})
                for div in divs_name:
                    title = div.find('h2').text.strip()
                    description = div.find('div', {"style": "grid-column: 1 / 3;    grid-row: 3 / 4; font-size: 18px"}).text.strip()
                    link= div.find('a')['href']
                    list_div.append({"title" : title, "description" : description, "link" : link, "slug": filename})
                divs_name = soup.find_all('div', {"class": "flex flex-row"})
                for div in divs_name:
                  try:
                    title = div.find('div', {"class": "text-xl font-semibold"})
                    if title is None:
                        continue
                    else:
                        title=title.text.strip()
                    try:
                        description = div.find('div', {"class": "line-clamp-3 text-gray-600"}).text.strip()
                    except:
                        description =""
                    link = div.find('a')['href']
                    list_div.append({"title" : title, "description" : description, "link" : link, "slug": filename})
                  except:
                    pass
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
