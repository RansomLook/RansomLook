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
                divs_name=soup.find_all('div', {"class": "MuiPaper-root MuiPaper-elevation MuiPaper-rounded MuiPaper-elevation1 MuiCard-root story-card css-76n6mc"})
                for div in divs_name:
                    title = div.find('div', {"class": "MuiTypography-root MuiTypography-h5 MuiTypography-gutterBottom css-bp7fp2"}).text.strip()
                    description = div.find('p',{"class":"MuiTypography-root MuiTypography-body2 css-1nwimy0"}).text.strip()
                    link = div.find('a')["href"]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})

                divs_name=soup.find_all('div', {"class": "col-lg-4 col-md-6"})
                for div in divs_name:
                    title = div.find('h5', {"class": "font-weight-normal mt-3"}).text.strip()
                    description = ""
                    link = div.find('a')["href"]
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
