import os
from bs4 import BeautifulSoup
from typing import Dict, List

def main() -> List[Dict[str, str]] :
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                divs_name=soup.find_all('div', {'class':'card p-2 h-100 shadow-none border'})
                for div in divs_name:
                    title = div.find('div',{'class':'card-body'}).a.text.strip()
                    description=''

                    if div.find('a')['href'] == 'http://vkvsgl7lhipjirmz6j5ubp3w3bwvxgcdbpi3fsbqngfynetqtw4w5hyd.onion/r/Vjl8Qnzlq9l3Oypw705dlj+hNfP2oQmDRV+CYqGWYljjfWrVI8P2kaIs9xEsjlica0fx7soU72FvuiA4gIKkdZdWhENUpF':
                         title='Your advertisement'
                    if div.find('a')['href'] == 'http://vkvsgl7lhipjirmz6j5ubp3w3bwvxgcdbpi3fsbqngfynetqtw4w5hyd.onion/r/CJfOSB16qhkTHoPKNZz5t2HL8s7dXDruplKPAQj2fwSB98D+5xpnlfcisOmL0InuT6kvYcafOxnhlEjjskRrUkVGTHFy':
                         title='Kominfo - 2'
                    if div.find('a')['href'] == 'http://vkvsgl7lhipjirmz6j5ubp3w3bwvxgcdbpi3fsbqngfynetqtw4w5hyd.onion/r/ckYfU3JoA8cRVvOkKxM5QFmwCFGurqEVS1pkFa8D8Lb2ZB3QCW7XYn649u6L2691j9bWUUUFPwtupHzw0dBkxOV1M3WDN4':
                         continue

                    link = div.find('a')['href']
                    list_div.append({"title" : title, "description" : description, 'link': link, 'slug': filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
