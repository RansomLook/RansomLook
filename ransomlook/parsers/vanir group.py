import os
from typing import Dict, List
import re
import json

def main() -> List[Dict[str, str]] :
    list_div=[]
    for filename in os.listdir('source'):
        if filename.startswith(__name__.split('.')[-1]+'-'):
            html_doc='source/'+filename
            file=open(html_doc,'r')
            if '.js' in filename:
                content = file.read()
                matches = re.search('projects:(.*)}}},P', content, re.IGNORECASE)
                myjson= matches.group(1).replace("projectName:", '"projectName":').replace("projectDescription:", '"projectDescription":').replace("githubLink:", '"githubLink":').replace("websiteLink:", '"websiteLink":').replace("tags:", '"tags":') # type: ignore

                data = json.loads(myjson)
                for entry in data:
                    title = entry['projectName'].strip()
                    description = entry['projectDescription'].strip()
                    list_div.append({"title" : title, "description" : description})
            file.close()
    print(list_div)
    return list_div
