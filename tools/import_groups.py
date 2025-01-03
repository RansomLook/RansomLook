#!/usr/bin/env python3
import json
import valkey
from ransomlook.default import get_socket_path

valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=0)

with open('data/groups.json') as json_file:
    data = json.load(json_file)

for item in data:
    name = item['name'].lower()
    item.pop('name')
    valkey_handle.set(name, json.dumps(item))


valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=3)

with open('data/markets.json') as json_file:
    data = json.load(json_file)

for item in data:
    name = item['name'].lower()
    item.pop('name')
    valkey_handle.set(name, json.dumps(item))

import collections
valkey_handle = valkey.Valkey(unix_socket_path=get_socket_path('cache'), db=2)
with open('data/posts.json') as json_file:
    data = json.load(json_file)
list_post=collections.defaultdict(list)
for item in data:
    name = item['group_name'].lower()
    item.pop('group_name')
    list_post[name].append(item)
for name in list_post:
     valkey_handle.set(name, json.dumps(list_post[name]))
