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
                divs_name=soup.find_all('article')
                for item in divs_name:
                    title = item.find('h2', {"class": "entry-title heading-size-1"}).a.string.text.strip()
                    description = item.find('div', {"class": "entry-content"}).p.text.strip()
                    link = item.find('h2', {"class": "entry-title heading-size-1"}).a['href']
                    list_div.append({'title':title, 'description': description, 'link': link, 'slug': filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
