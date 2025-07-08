import os
import re
from typing import Dict, List
import json

def main() -> List[Dict[str, str]] :
    list_div=[]
    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                file=open(html_doc,'r')
                js_content = file.read()
                if 'leaks-data' in filename:
                    match = re.search(r"let\s+leaks\s*=\s*(\[[\s\S]*?\])\s*,", js_content)
                    if match:
                        leaks_json = match.group(1)
                        leaks_json_clean = re.sub(r'(\{|,)\s*(\w+)\s*:', r'\1"\2":', leaks_json)
                        data = json.loads(leaks_json_clean)
                        for entry in data:
                            title = entry['title'].strip()
                            description = entry['description'].strip()
                            link = '/'+entry['id'].strip()
                            list_div.append({'title':title, 'description': description, 'link': link, 'slug': filename})
                file.close()
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)

    return list_div
