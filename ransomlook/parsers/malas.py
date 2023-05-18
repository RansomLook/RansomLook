
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
                if filename.endswith('xml.html'):
                    items = soup.find_all('item')
                    for item in items:
                        title = item.title.text
                        description =  item.description.text
                        list_div.append({"title" : title, "description" : description})
                else:
                    liste = soup.find('ul', {"class":"list"} )
                    divs_name=liste.find_all('li') # type: ignore
                    for div in divs_name:
                        title = div.a['title'].strip()
                        description = ""
                        list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    list_div = []
    return list_div
