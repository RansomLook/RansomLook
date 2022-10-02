#!/usr/bin/env python3
import json
import redis
import requests

from ransomlook.default import get_socket_path, get_config

red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)

malpedia = get_config('generic','malpedia')
print(malpedia)

response =  requests.get('https://malpedia.caad.fkie.fraunhofer.de/api/get/families', headers={'Authorization': 'apitoken '+malpedia})
families = json.loads(response.text)

keys = red.keys()
for family in families:
    names = []
    names.append(families[family]['common_name'])
    names.extend(families[family]['alt_names'])
    names = [x.lower() for x in names]
    for key in keys:
        if key.decode().lower() in names:
           for alter in families[family]['alt_names']:
               print(alter)
           for url in families[family]['urls']:
               print(url)
           group = json.loads(red.get(key))
           group['meta'] = families[family]['description']
           group['profile'].extend(families[family]['urls'])
           red.set(key,json.dumps(group))
        #exit()
