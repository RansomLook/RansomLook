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
                divs_name=soup.find_all('a', {"class":"flex flex-col justify-between w-full h-56 border-t-4 border-2 border-t-green-500 dark:border-gray-900 dark:border-t-green-500 rounded-[20px] bg-white dark:bg-navy-800"})
                for div in divs_name:
                    section = div.find('span',{"class": "dark:text-gray-600"})
                    title = section.text.strip()
                    description = div.find('span',{"class": "text-sm dark:text-gray-600"}).text.strip()
                    list_div.append({"title" : title, "description" : description})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
