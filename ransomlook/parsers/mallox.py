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
                divs_name=soup.find_all('div', {"class": "card mb-4 box-shadow"})
                for div in divs_name:
                    title = div.find('h4',{"class": "card-title"}).text.strip()
                    description = ''
                    for p in div.find_all('p'):
                        description+=p.text+'\n'
                    linktmp = div.find('a', {"class" :"btn btn-primary btn-sm"})
                    if linktmp != None:
                        link = linktmp['href']
                        list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})
                    else:
                        list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
