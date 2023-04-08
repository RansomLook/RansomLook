import json
import redis
import requests

from ransomlook.default.config import get_config, get_socket_path
from ransomlook.rocket import rocketnotifyleak

def main() -> None :

    red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=10)
    keys = red.keys()
    rftoken = get_config('generic','rf')

    header = { "x-RFToken": rftoken,
           "Content-Type": "application/json" }

    query = { "names": [""],
          "limit": 10000}

    r_details=requests.post("https://api.recordedfuture.com/identity/metadata/dump/search",headers=header,json=query)
    temp = r_details.json()

    for entry in temp['dumps']:
        next = False
        for key in keys:
            if entry['name'].encode == key:
                next = True
                continue
        if next == False :
            red.set(entry['name'], json.dumps(entry))

if __name__ == '__main__':
    main()
