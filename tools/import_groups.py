#!/usr/bin/env python3
import collections
import json

import valkey

from ransomlook.default import DB_GROUPS, DB_MARKETS, DB_POSTS, get_socket_path

red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_GROUPS)

with open("data/groups.json") as json_file:
    data = json.load(json_file)

for item in data:
    name = item["name"].lower()
    item.pop("name")
    red.set(name, json.dumps(item))


red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_MARKETS)

with open("data/markets.json") as json_file:
    data = json.load(json_file)

for item in data:
    name = item["name"].lower()
    item.pop("name")
    red.set(name, json.dumps(item))

red = valkey.Valkey(unix_socket_path=get_socket_path("cache"), db=DB_POSTS)
with open("data/posts.json") as json_file:
    data = json.load(json_file)
list_post = collections.defaultdict(list)
for item in data:
    name = item["group_name"].lower()
    item.pop("group_name")
    list_post[name].append(item)
for name in list_post:
    red.set(name, json.dumps(list_post[name]))
