import os
from bs4 import BeautifulSoup # type: ignore

def main():
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name=soup.find_all('div', {"class": "MainCard_card__2aCY4"})
                for div in divs_name:
                    title = div.find('h4',{"class": "MainCard_card__title__jdBK+"}).text.strip()
                    description = div.find('div',{"class": "MainCard_card__body_column__rZHSt"}).find('p',{"class" : "MainCard_card__body_text__4AtzB"}).text.strip()
                    list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
