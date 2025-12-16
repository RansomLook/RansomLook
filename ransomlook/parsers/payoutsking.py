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
                tbody=soup.find('tbody', {"id": "table"})
                if tbody:
                    trs = tbody.find_all('tr') # type: ignore
                    for tr in trs:
                        try:
                            tds = tr.find_all('td')
                            title = tds[1].text.strip()
                            description = tds[2].text.strip()
                            link=tds[1].a['hx-post']
                            list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                        except:
                            pass
                companies = soup.find_all('company-chevron')
                print(companies)
                for company in companies:
                    title = company.text.strip()
                    list_div.append({"title" : title, "description" : ""})
                file.close()

        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
