import os
from bs4 import BeautifulSoup

def main():
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name=soup.find_all('h2', {"class": "type-list-title"})
                for div in divs_name:
                    for item in div.contents :
                        list_div.append({"title": item.text.strip(), "description": ""})
                divs_name=soup.find_all("article", {"class": "post"})
                for div in divs_name:
                    data = div.find_all("code", {"class": "language-text"})
                    print(data)
                    title = data[0].text.strip()
                    description = data[1].text.strip()
                    list_div.append({"title": title, "description": description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
