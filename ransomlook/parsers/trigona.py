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

                div=soup.find('div', {"class": "grid"})
                divs_name = div.find_all('a')
                for div in divs_name:
                    title = div.find('div', {"class": "grid-caption__title"}).contents[0].strip()
                    description = ''
                    link = div['href']
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
