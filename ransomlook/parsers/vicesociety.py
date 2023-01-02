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
                divs_name=soup.find_all('td',{"valign":"top"})
                for div in divs_name:
                    title = div.find("font", {"size":4}).text.strip()
                    for description in div.find_all("font", {"size":2, "color":"#5B61F6"}):
                        if not description.b.text.strip().startswith("http"):
                            list_div.append({"title" : title, "description" : description.b.text.strip()})
                            break
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
