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
                divs_name=soup.find_all('center')
                for div in divs_name:
                    try:
                        title = div.find('p', {"class": "h1"}).text
                        description = div.find("p", {"class": "description"}).text.strip()
                        list_div.append({"title" : title, "description" : description})
                    except:
                        pass
                divs_name=soup.find_all('div', {"class": "item-details"})
                for div in divs_name:
                    title = div.find('h3').text
                    description = div.find("p").text.strip()
                    list_div.append({"title" : title, "description" : description})
                file.close()
                divs_name =  soup.find_all('table')
                for div in divs_name:
                    title = div.find('img')['src'].split('/')[-1].split('.')[0]
                    description = div.find('p', {"class": "description"}).text.strip()
                    link = div.find('p', {"class": "textprice"}).a['href']
                    list_div.append({"title" : title, "description" : description, "link": link, "slug": filename})

        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
