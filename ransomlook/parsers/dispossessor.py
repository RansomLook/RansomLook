import os
from bs4 import BeautifulSoup
from typing import Dict, List
import json
from datetime import datetime

def main() -> List[Dict[str, str]] :
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                soup=BeautifulSoup(file,'html.parser')
                if 'getallblogs' in filename:
                    print(filename)
                    jsonpart= soup.pre.contents # type: ignore
                    data = json.loads(jsonpart[0]) # type: ignore
                    for entry in data['data']['items']:
                       date_str = entry['uploaded_date']
                       date_obj = datetime.strptime(date_str, '%d %b, %Y %H:%M:%S %Z')
                       formatted_date = date_obj.strftime('%Y-%m-%d %H:%M:%S.%f')
                       list_div.append({"title":entry['company_name'].strip(),"description":entry["description"].strip(), "link":entry["id"], "slug": filename, "date":formatted_date})
                file.close()
        except:
            print("can not open " + filename)
            pass
    print(list_div)
    return list_div
