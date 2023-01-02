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
                divs_name=soup.find_all('div', {"class": "relative bg-white rounded-lg shadow dark:bg-gray-700"})
                for div in divs_name:
                    title = div.find('h3').text.strip().split('\n')[0].strip()
                    description = div.find('p', {'class':"break-all"}).text.strip()
                    list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    return list_div
