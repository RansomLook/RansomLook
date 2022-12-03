#!/usr/bin/env python3
import json
import redis
from ransomlook.default import get_socket_path
import requests

remote_instance='https://www.ransomlook.io'

print('Importing Groups')
groups = requests.get(remote_instance +'/export/0').json()
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=0)
for key in groups:
    red.set(key, json.dumps(groups[key]))

print('Importing Posts')
groups = requests.get(remote_instance +'/export/2').json()
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
for key in groups:
    red.set(key, json.dumps(groups[key]))

print('Importing Forums')
groups = requests.get(remote_instance +'/export/3').json()
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=3)
for key in groups:
    red.set(key, json.dumps(groups[key]))

print('Importing Leaks')
groups = requests.get(remote_instance +'/export/4').json()
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=4)
for key in groups:
    red.set(key, json.dumps(groups[key]))

print('Importing Telegram channels')
groups = requests.get(remote_instance +'/export/5').json()
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
for key in groups:
    red.set(key, json.dumps(groups[key]))

print('Importing Telegram message')
groups = requests.get(remote_instance +'/export/6').json()
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=6)
for key in groups:
    red.set(key, json.dumps(groups[key]))



'''

with open('data/groups.json') as json_file:
    data = json.load(json_file)

for item in data:
    name = item['name'].lower()
    item.pop('name')
    red.set(name, json.dumps(item))


red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=3)

with open('data/markets.json') as json_file:
    data = json.load(json_file)

for item in data:
    name = item['name'].lower()
    item.pop('name')
    red.set(name, json.dumps(item))

import collections
red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)
with open('data/posts.json') as json_file:
    data = json.load(json_file)
list_post=collections.defaultdict(list)
for item in data:
    name = item['group_name'].lower()
    item.pop('group_name')
    list_post[name].append(item)
for name in list_post:
     red.set(name, json.dumps(list_post[name]))
'''
