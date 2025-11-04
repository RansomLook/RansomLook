#!/usr/bin/env python3
import json
import redis
from ransomlook.default import get_socket_path
import requests

remote_instance='https://www.ransomlook.io/api'

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
