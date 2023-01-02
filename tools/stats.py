#!/usr/bin/env python3
import redis
import os
from ransomlook.default import get_socket_path, get_config

import json
import csv
import datetime

from typing import Dict

f = open('stats.csv','w')
header = ['Group', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
writer = csv.writer(f)
writer.writerow(header)


red = redis.Redis(unix_socket_path=get_socket_path('cache'), db=2)

postnum: Dict = {}
for key in red.keys():
    postnum[key]={}
    posts =json.loads(red.get(key)) # type: ignore
    for post in posts:
        if post['discovered'][:7] not in postnum[key]:
            postnum[key][post['discovered'][:7]]=1
        else :
            postnum[key][post['discovered'][:7]]+=1

    row = []
    row.append(key.decode())

    for i in range(1,13):
        x = datetime.datetime(2022, i,1).strftime("%Y-%m")
        if x in postnum[key] :
            row.append(postnum[key][x])
        else :
            row.append('0')
    writer.writerow(row)
