#!/usr/bin/env python3
import redis
import os
from ransomlook.default import get_socket_path, get_config

from ransomlook.rocket import rocketnotifyleak

import json

red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=5)
#    red.set(data,json.dumps(datas))

with open('data/telegram.txt', 'r') as file:
    lines = file.readlines()
    for line in lines:
        data = {}
        d=line.split('|')
        data['name']=d[1].strip('/').split('/')[-1]

        data['meta']=d[3]
        data['link']=d[1]
        red.set(data['name'],json.dumps(data))
